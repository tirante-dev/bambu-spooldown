# spooldown

Counts Bambu Lab print jobs down against
[Spoolman](https://github.com/Donkie/Spoolman) spool inventory.

The AMS only knows how much filament remains on Bambu RFID spools; third-party
spools report nothing. spooldown watches the printer's local MQTT report
stream, and when a print finishes it looks up the sliced per-filament weight
(from the 3MF for LAN prints, from the Bambu cloud task API for cloud prints)
and records that usage against the matching Spoolman spools. Cancelled prints
are recorded proportionally to their completion percentage.

Spool matching, per AMS tray used by the job:

1. RFID spools: the tray uuid against Spoolman's `tag` extra field (as written
   by [bambulab-ams-spoolman-filamentstatus](https://github.com/Rdiger-36/bambulab-ams-spoolman-filamentstatus)).
2. Third-party spools: the spool whose location is `<PRINTER_NAME> - A<tray>`.
   Set that location on the spool in Spoolman by hand once, when you load it.

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

Without `BAMBU_CLOUD_TOKEN`, cloud-sent prints log a warning and record
nothing; on current firmware the printer does not expose the sliced file
locally for them.

## Run

```
docker run -e PRINTER_HOST=... -e PRINTER_SERIAL=... -e ACCESS_CODE=... \
  -e SPOOLMAN_URL=http://spoolman:8000 -v spooldown-data:/data \
  ghcr.io/tirante-dev/spooldown:latest
```

`GET :8080/` answers 200 while the MQTT stream is live, 503 when stale.

## Develop

`uv sync`, then `make check` (ruff format check, ruff lint, strict mypy,
pytest). CI runs the same and publishes the image on merge to `main`.
