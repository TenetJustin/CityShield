# Deploy on IBM LinuxONE

CityShield uses an OCI container based on Red Hat UBI Python and is designed to run on `s390x` LinuxONE as well as local development machines. The image builds the React console on LinuxONE and serves it from the same origin as the API at `/`.

## Update the existing Community Cloud VM

The current CityShield VM is named `cityshield_linuxone`. Its SSH user is `linux1` and its address is shown under **Virtual Servers → Manage Instances**. From a Mac with the matching private key:

```bash
ssh -i ~/.ssh/cityshield_linuxone -o IdentitiesOnly=yes linux1@<VM_IP>
```

Enter the **private key passphrase** at the SSH prompt. The private key is encrypted; noninteractive SSH fails without this passphrase. Never paste the passphrase into this repository or share the private key with teammates.

On the VM, use the latest `main` commit:

```bash
if [ -d "$HOME/CityShield/.git" ]; then
  cd "$HOME/CityShield" && git pull --ff-only origin main
else
  git clone https://github.com/TenetJustin/CityShield.git "$HOME/CityShield"
  cd "$HOME/CityShield"
fi
git rev-parse --short HEAD
uname -m
podman build -f Containerfile.linuxone -t cityshield:latest .
podman rm -f cityshield 2>/dev/null || true
podman run -d --name cityshield --restart=unless-stopped \
  -p 127.0.0.1:8000:8000 \
  -v cityshield-runtime:/opt/app-root/src/backend/data/runtime \
  cityshield:latest
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/ >/dev/null
python3 scripts/smoke_test.py http://127.0.0.1:8000
```

If `podman` or `git` is missing on RHEL, install it with `sudo dnf install -y podman git` and rerun the commands. Check `podman logs cityshield` if a command fails.

The API has unauthenticated demo write endpoints. Keep port 8000 bound to `127.0.0.1` until TLS and access control are configured. To view the full site securely from your Mac, open another local terminal:

```bash
ssh -i ~/.ssh/cityshield_linuxone -o IdentitiesOnly=yes \
  -L 8000:127.0.0.1:8000 linux1@<VM_IP>
```

Then open `http://127.0.0.1:8000/`. Each teammate needs their **own** SSH access and tunnel to view this private deployment. A public team URL requires an authenticated HTTPS ingress; do not open port 8000 directly to the internet.

## LinuxONE evidence for the submission

Capture the following from the actual instance:

1. `uname -m` showing `s390x`;
2. container build/run output;
3. `/health` response and model version;
4. one stream replay, forecast run ID and decision audit ID;
5. resource/latency observations from `/api/v1/metrics`;
6. a screenshot of the console connected to the LinuxONE API.

Do not claim LinuxONE execution until this evidence has been collected from the allocated environment.

## Production hardening beyond the Datathon

Terminate TLS at an approved ingress, authenticate write endpoints, use a managed persistent database/WORM audit target, define backups and retention, add rate limits, use signed images, scan the image, and integrate the local authority's incident-command process.

