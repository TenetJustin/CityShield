# Public HTTPS access from IBM LinuxONE

CityShield's application, API, data and prediction process run in the
`cityshield-api` container on the IBM LinuxONE `s390x` host. The public tunnel
only carries HTTPS traffic to the loopback service at `127.0.0.1:8000`.

## Install or refresh the public demo tunnel

On LinuxONE:

```bash
cd ~/CityShield
bash scripts/setup_linuxone_public_tunnel.sh
```

The script builds the official `cloudflared` source natively for `s390x`,
installs a user-level systemd service and prints the public HTTPS address.
User lingering is enabled on the competition host, so the service stays up
after the SSH session closes.

## Read the current address and status

```bash
cat ~/cityshield-public/public-url.txt
systemctl --user status cityshield-public.service --no-pager
curl -fsS http://127.0.0.1:8000/health
```

## Restart

```bash
systemctl --user restart cityshield-public.service
```

After a restart, wait several seconds and read the new address from:

```bash
cat ~/cityshield-public/public-url.txt
```

## Address lifetime

The no-account `trycloudflare.com` address is intended for a competition demo
and can change whenever the tunnel process restarts. A stable submission URL
requires a named Cloudflare Tunnel, a domain in a Cloudflare account and its
tunnel token. The origin remains the same LinuxONE service in either setup.

