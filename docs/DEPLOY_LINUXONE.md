# Deploy on IBM LinuxONE

CityShield uses an OCI container based on Red Hat UBI Python and is designed to run on `s390x` LinuxONE as well as local development machines.

## Build and run

```bash
podman build -f Containerfile.linuxone -t cityshield:0.2.0 .
podman run --rm \
  --name cityshield \
  -p 8000:8000 \
  --env-file .env \
  -v cityshield-runtime:/opt/app-root/src/backend/data/runtime \
  cityshield:0.2.0
```

Verify:

```bash
curl http://127.0.0.1:8000/health
python scripts/smoke_test.py http://127.0.0.1:8000
```

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

