# bambu-spooldown

Counts Bambu Lab print jobs down against
[Spoolman](https://github.com/Donkie/Spoolman) spool inventory.

The AMS only knows how much filament remains on Bambu RFID spools; third-party
spools report nothing. bambu-spooldown watches the printer's local MQTT report
stream, and when a print finishes it looks up the sliced per-filament weight
and records that usage against the matching Spoolman spools. Cancelled prints
are recorded proportionally to their completion percentage. A persisted ledger
guarantees each job is counted exactly once.

Usage evidence, per print:

- LAN-sent prints: the 3MF is fetched from the printer over FTPS and
  `Metadata/slice_info.config` gives exact grams per filament.
- Cloud-sent prints: the printer does not expose the sliced file locally, so
  weights come from the Bambu cloud task API. This needs `BAMBU_CLOUD_TOKEN`;
  without it, cloud prints log a warning and record nothing.

## What you need

- A Bambu Lab printer reachable on your LAN, plus its LAN access code
  (printer screen: Settings, Network) and serial number.
- A running Spoolman instance.
- For Bambu RFID spools, run
  [bambulab-ams-spoolman-filamentstatus](https://github.com/Rdiger-36/bambulab-ams-spoolman-filamentstatus)
  with `SET_LOCATION=true` alongside: it creates the spools in Spoolman with
  their RFID tag in the `tag` extra field, which is how bambu-spooldown
  matches them. bambu-spooldown never creates spools; it only records usage.

## Spool matching

For each AMS tray a job used:

1. RFID spools match on the tray uuid against Spoolman's `tag` extra field.
2. Third-party spools (no RFID) match on the spool whose location is
   `<PRINTER_NAME> - A<tray>`, e.g. `3DP-31B-432 - A3` for the fourth slot of
   the first AMS. Create the spool in Spoolman yourself and set that location
   once, when you load it.

## Run

Two artifacts are published to `registry.ahkc.win` per release: the container
image (`bambu-spooldown/bambu-spooldown`, semver tags plus `latest`) and a
Helm chart (`oci://registry.ahkc.win/bambu-spooldown/charts/bambu-spooldown`).

### Docker

```
docker run -d --name bambu-spooldown \
  -e PRINTER_HOST=192.168.1.50 \
  -e PRINTER_SERIAL=01P00A000000000 \
  -e ACCESS_CODE=12345678 \
  -e PRINTER_NAME=3DP-31B-432 \
  -e SPOOLMAN_URL=http://spoolman:8000 \
  -v bambu-spooldown-data:/data \
  registry.ahkc.win/bambu-spooldown/bambu-spooldown:latest
```

### Docker Compose

```yaml
services:
  bambu-spooldown:
    image: registry.ahkc.win/bambu-spooldown/bambu-spooldown:latest
    restart: unless-stopped
    environment:
      PRINTER_HOST: 192.168.1.50
      PRINTER_SERIAL: 01P00A000000000
      ACCESS_CODE: "12345678"
      PRINTER_NAME: 3DP-31B-432
      SPOOLMAN_URL: http://spoolman:8000
      BAMBU_CLOUD_TOKEN: ${BAMBU_CLOUD_TOKEN:-}
    volumes:
      - data:/data
volumes:
  data:
```

### Helm

Create a Secret holding `ACCESS_CODE` (and optionally `BAMBU_CLOUD_TOKEN`),
then:

```
helm install spooldown oci://registry.ahkc.win/bambu-spooldown/charts/bambu-spooldown \
  --set printer.host=192.168.1.50 \
  --set printer.serial=01P00A000000000 \
  --set printer.name=3DP-31B-432 \
  --set spoolman.url=http://spoolman:8000 \
  --set existingSecret=spooldown-env
```

The chart source is [charts/bambu-spooldown](charts/bambu-spooldown); see its
[values.yaml](charts/bambu-spooldown/values.yaml) for every knob (image tag
defaults to the chart's appVersion, persistence, resources, extraEnv).

`GET :8080/` answers 200 while the MQTT stream is live and 503 when it has
gone stale, so it works as a container healthcheck or Kubernetes probe.

Releases are cut by release-please; app releases publish the image, chart
releases publish the chart, both to the same Harbor project.

## Configuration

| Env | Required | Meaning |
|---|---|---|
| `PRINTER_HOST` | yes | Printer IP or hostname |
| `PRINTER_SERIAL` | yes | Printer serial number |
| `ACCESS_CODE` | yes | LAN access code (printer screen: Settings, Network) |
| `SPOOLMAN_URL` | yes | Spoolman base URL, e.g. `http://spoolman:8000` |
| `PRINTER_NAME` | no | Location-convention prefix, e.g. `3DP-31B-432` |
| `BAMBU_CLOUD_TOKEN` | no | Bearer token for cloud-print usage lookup |
| `LEDGER_PATH` | no | Processed-jobs file, default `/data/ledger.json` |
| `PARTIAL_ON_CANCEL` | no | `false` skips cancelled prints, default `true` |
| `HEALTH_PORT` | no | Liveness HTTP port, default `8080` |
| `LOG_LEVEL` | no | Python log level, default `INFO` |

## Getting a cloud token

Bambu's email-code login works even for accounts that sign in with Apple or
Google, and involves no password:

```
curl -X POST https://api.bambulab.com/v1/user-service/user/sendemail/code \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","type":"codeLogin"}'

curl -X POST https://api.bambulab.com/v1/user-service/user/login \
  -H 'Content-Type: application/json' \
  -d '{"account":"you@example.com","code":"<code from email>","loginType":"verifyCode"}'
```

The second call returns `accessToken`; store it somewhere safe and pass it as
`BAMBU_CLOUD_TOKEN`. Tokens expire after roughly 90 days; repeat the flow to
get a new one.

## Limitations

- One printer per instance; run one container per printer.
- Cancelled prints are estimated by completion percentage, which slightly
  overstates filaments used late in a multi-material print.
- External spool holder prints match a tray only when the printer reports a
  mapping for them; otherwise they are logged and skipped.

## Develop

`uv sync`, then `make check` (ruff format check, ruff lint, strict mypy,
pytest). CI runs the same and publishes the image on merge to `main`.
