#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ $(uname -m) != s390x ]]; then
  echo "Run this script on the IBM LinuxONE (s390x) VM." >&2
  exit 1
fi

commit=$(git rev-parse --short HEAD)
image="localhost/cityshield:$commit"
runtime_path=/opt/app-root/src/backend/data/runtime
runtime_env_file=${CITYSHIELD_ENV_FILE:-"$HOME/.config/cityshield/runtime.env"}
env_args=()
if [[ -f $runtime_env_file ]]; then
  env_args=(--env-file "$runtime_env_file")
fi

wait_for_health() {
  local port=$1
  for _ in {1..30}; do
    if curl -fsS --max-time 2 "http://127.0.0.1:$port/health" >/dev/null; then
      return 0
    fi
    sleep 1
  done
  return 1
}

wait_for_port_release() {
  local port=$1
  for _ in {1..30}; do
    if ! ss -H -ltn "sport = :$port" | grep -q .; then
      return 0
    fi
    sleep 1
  done
  echo "Port $port did not become available after the old container stopped." >&2
  return 1
}

run_production() {
  podman run -d --name cityshield-api --restart=unless-stopped \
    -p 127.0.0.1:8000:8000 \
    -v "cityshield-runtime:$runtime_path:Z" \
    "${env_args[@]}" \
    "$1"
}

echo "Building CityShield $commit on $(uname -m)..."
podman build -f Containerfile.linuxone -t "$image" .

# Exercise the new image on an isolated port and volume before touching the site.
podman rm -f cityshield-candidate >/dev/null 2>&1 || true
cleanup() { podman rm -f cityshield-candidate >/dev/null 2>&1 || true; }
trap cleanup EXIT
podman run -d --name cityshield-candidate \
  -p 127.0.0.1:18001:8000 \
  -v "cityshield-validation:$runtime_path:Z" \
  "${env_args[@]}" \
  "$image"
wait_for_health 18001
curl -fsS http://127.0.0.1:18001/ >/dev/null
curl -fsS http://127.0.0.1:18001/api/v1/paradise/geography >/dev/null
python3 scripts/smoke_test.py http://127.0.0.1:18001
cleanup
trap - EXIT

previous_image=$(podman inspect --format '{{.Image}}' cityshield-api 2>/dev/null || true)
podman rm -f cityshield-api >/dev/null 2>&1 || true
wait_for_port_release 8000

if ! run_production "$image" || ! wait_for_health 8000; then
  echo "New container failed. Restoring the previous image..." >&2
  podman rm -f cityshield-api >/dev/null 2>&1 || true
  if [[ -n $previous_image ]]; then
    wait_for_port_release 8000
    run_production "$previous_image"
  fi
  exit 1
fi

podman tag "$image" localhost/cityshield:latest
echo "CityShield $commit is serving on LinuxONE at 127.0.0.1:8000."
curl -fsS http://127.0.0.1:8000/health
printf '\n'
