#!/usr/bin/env bash
set -euo pipefail

CLOUDFLARED_TAG=${CLOUDFLARED_TAG:-2026.9.3}
PUBLIC_ROOT=${PUBLIC_ROOT:-"$HOME/cityshield-public"}
APP_URL=${APP_URL:-http://127.0.0.1:8000}
SERVICE_NAME=cityshield-public.service

if [[ $(uname -m) != "s390x" ]]; then
  echo "This installer is intended for the IBM LinuxONE s390x host." >&2
  exit 1
fi

command -v podman >/dev/null
command -v systemctl >/dev/null
curl -fsS "$APP_URL/health" >/dev/null

mkdir -p "$PUBLIC_ROOT/bin" "$PUBLIC_ROOT/logs" "$HOME/.config/systemd/user"

if [[ ! -d "$PUBLIC_ROOT/cloudflared-src/.git" ]]; then
  git clone --depth 1 --branch "$CLOUDFLARED_TAG" \
    https://github.com/cloudflare/cloudflared.git \
    "$PUBLIC_ROOT/cloudflared-src"
else
  git -C "$PUBLIC_ROOT/cloudflared-src" fetch --depth 1 origin \
    "refs/tags/$CLOUDFLARED_TAG:refs/tags/$CLOUDFLARED_TAG"
  git -C "$PUBLIC_ROOT/cloudflared-src" checkout --detach "$CLOUDFLARED_TAG"
fi

# Cloudflare does not publish a Linux s390x image, so build the official source
# with Red Hat's native s390x Go toolset. Root here is rootless-Podman root and
# only writes into the current user's PUBLIC_ROOT directory.
podman run --rm --user 0 \
  -v "$PUBLIC_ROOT/cloudflared-src:/src:Z" \
  -v "$PUBLIC_ROOT/bin:/out:Z" \
  registry.access.redhat.com/ubi9/go-toolset:latest \
  bash -lc 'cd /src && go build -buildvcs=false -o /out/cloudflared ./cmd/cloudflared'
chmod 755 "$PUBLIC_ROOT/bin/cloudflared"

cat >"$PUBLIC_ROOT/run-tunnel.sh" <<EOF
#!/usr/bin/env bash
set -u
: >"$PUBLIC_ROOT/logs/tunnel.log"
rm -f "$PUBLIC_ROOT/public-url.txt"
"$PUBLIC_ROOT/bin/cloudflared" tunnel \
  --no-autoupdate \
  --edge-ip-version 4 \
  --protocol http2 \
  --url "$APP_URL" >"$PUBLIC_ROOT/logs/tunnel.log" 2>&1 &
tunnel_pid=\$!
trap 'kill "\$tunnel_pid" 2>/dev/null || true; wait "\$tunnel_pid" 2>/dev/null || true; exit 0' TERM INT
for _ in {1..60}; do
  public_url=\$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' \
    "$PUBLIC_ROOT/logs/tunnel.log" | tail -1 || true)
  if [[ -n \$public_url ]]; then
    printf '%s\\n' "\$public_url" >"$PUBLIC_ROOT/public-url.txt"
    break
  fi
  sleep 1
done
wait "\$tunnel_pid"
EOF
chmod 755 "$PUBLIC_ROOT/run-tunnel.sh"

cat >"$HOME/.config/systemd/user/$SERVICE_NAME" <<EOF
[Unit]
Description=CityShield public HTTPS tunnel from IBM LinuxONE
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=$PUBLIC_ROOT/run-tunnel.sh
Restart=always
RestartSec=5
TimeoutStopSec=10

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now "$SERVICE_NAME"
rm -f "$PUBLIC_ROOT/public-url.txt"
systemctl --user restart "$SERVICE_NAME"

public_url=""
for _ in {1..30}; do
  public_url=$(cat "$PUBLIC_ROOT/public-url.txt" 2>/dev/null || true)
  if [[ -n $public_url ]]; then
    break
  fi
  sleep 1
done

if [[ -z $public_url ]]; then
  echo "Tunnel started but no public URL was found." >&2
  systemctl --user status "$SERVICE_NAME" --no-pager >&2 || true
  exit 1
fi

public_ready=0
for _ in {1..12}; do
  if curl -fsS --max-time 15 "$public_url/health" >/dev/null; then
    public_ready=1
    break
  fi
  sleep 5
done
if [[ $public_ready -ne 1 ]]; then
  echo "Tunnel is connected, but its public DNS name is not reachable yet." >&2
  exit 1
fi
printf '%s\n' "$public_url" | tee "$PUBLIC_ROOT/public-url.txt"
echo "CityShield is public at $public_url and served by $APP_URL on LinuxONE."

