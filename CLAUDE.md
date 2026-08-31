# CLAUDE.md

Guidance for working in this repo. `AGENTS.md` is intentionally a symlink to
this file so Claude and Codex read one instruction source; edit `CLAUDE.md`,
never replace the symlink with a second copy.

## What this is

**bambu-spooldown**: a small daemon that watches one Bambu Lab printer over local
MQTT and decrements [Spoolman](https://github.com/Donkie/Spoolman) spools by
the sliced per-filament weight when a print finishes. It exists because the
AMS only reports remaining filament for Bambu RFID spools; third-party spools
get no automatic tracking from AMS-state bridges. Solo-developer project,
deployed on a homelab Kubernetes cluster via the `tirante-dev/homelab` repo.

Ad-hoc scope: no roadmap, no spec tree. Keep it one printer, one Spoolman,
a few hundred lines.

## How it works

```
printer MQTT report ──▶ tracker (job state machine)
                              │ job FINISH / FAILED
                              ▼
                   usage evidence, first match wins:
                     1. LAN print: 3MF via FTPS, slice_info.config used_g
                     2. cloud print: Bambu cloud task API (needs token)
                              ▼
        per-filament grams ── job `mapping` ──▶ global tray index
                              ▼
        Spoolman spool via RFID tag extra, else location
        "<PRINTER_NAME> - A<tray>" ──▶ PUT /spool/{id}/use
```

- `tracker.py` deep-merges partial MQTT payloads; a `pushall` is requested on
  every connect so state starts from a full snapshot.
- `usage.py` parses `Metadata/slice_info.config` and queries the cloud task
  list.
- `spoolman.py` resolves trays to spools. The location convention matches
  what the Rdiger-36 AMS bridge writes (`SET_LOCATION=true`); third-party
  spools must have their location set by hand in Spoolman.
- `ledger.py` persists processed task ids; a job decrements exactly once.
- `mapper.py` auto-maps third-party trays (material, then color distance
  under 60 to break ties) and only when exactly one candidate remains;
  anything ambiguous or a stale mapping goes to `notify.py` (ntfy POST,
  debounced on the unmapped-set signature) and the `/map` page in `web.py`.
- `cloud.py` owns the Bambu cloud token pair: env tokens only seed an empty
  store (a self-managed Kubernetes Secret in-cluster, a JSON file otherwise),
  refresh happens on 401 and proactively past 30 days. The store Secret is
  deliberately separate from the sealed seed secret so ArgoCD and
  sealed-secrets never reconcile the rotated values away.
- Cancelled/failed prints decrement proportionally to `mc_percent`
  (`PARTIAL_ON_CANCEL=false` disables).

## Hard-won protocol facts (verified against an H2C, firmware 01.02.00.00)

- FTPS is implicit TLS on 990, login `bblp` / access code, and the data
  channel **must resume the control connection's TLS session** or the server
  answers `522`. `printer.ImplicitFTPS` carries that; don't simplify it away.
- Cloud prints (`print_type: "cloud"`, `sdcard: false`) never appear on the
  FTPS share on this firmware. Only the cloud task API can give their weight.
- The report's `mapping` array is filament id order to global tray index;
  `-1` marks unused. `tray_uuid` of all zeros marks a third-party spool.
- Spoolman stores extra fields JSON-encoded: the tag extra reads as
  `'"ABC..."'` and must be json-decoded before comparing.

## Build / run

- `make check` runs everything CI runs: ruff format check, ruff lint, mypy
  (strict), pytest. `uv sync` first.
- Config is env-only: `PRINTER_HOST`, `PRINTER_SERIAL`, `ACCESS_CODE`,
  `SPOOLMAN_URL` required; `PRINTER_NAME`, `BAMBU_CLOUD_TOKEN`, `LEDGER_PATH`,
  `PARTIAL_ON_CANCEL`, `HEALTH_PORT`, `LOG_LEVEL` optional.
- Releases: release-please (conventional commits; PR titles are enforced and
  become the squash commit). App releases push
  `registry.ahkc.win/bambu-spooldown/bambu-spooldown` (semver + `latest`);
  chart releases push the chart under `charts/bambu-spooldown` to
  `oci://registry.ahkc.win/bambu-spooldown/charts`. Semver image tags are
  immutable in Harbor. CI runs on the `bambu-spooldown` self-hosted runner
  scale set from the homelab cluster.
- The homelab cluster consumes the chart via its ApplicationSet; deployment
  values live in the homelab repo, not here.

## Code comments and prose

- Explain why, not what. Delete any comment restating the next line.
- Doc-comment modules and public functions; state units, edge cases, and
  invariants a reader cannot infer.
- No historical breadcrumbs ("formerly", "was", "changed from"); the tree
  describes the system as it is now.
- No em dashes in prose; use a comma, colon, parentheses, or a new sentence.
