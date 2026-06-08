# 115 Sync Console

A self-hosted scanner, differential downloader, and live web dashboard for
syncing a selected 115 cloud directory to local storage.

![Dashboard](assets/sync-bg.png)

## Features

- Recursively scans one configured 115 directory.
- Builds the next manifest separately and promotes it atomically after a
  successful scan.
- Downloads files that are missing locally or have a different size.
- Skips complete local files and avoids duplicate downloads.
- Supports multiple file workers and ranged HTTP transfers.
- Provides live scan, manifest, download, speed, task, log, and cookie status.
- Supports remote cookie replacement and manual scan/sync actions.
- Protects all write APIs with an optional management token.
- Supports include filters, excluded paths, and priority keywords.

## Important Notice

This project uses the unofficial `p115client` package and 115 web APIs. Those
APIs may change without notice. Use this project only with your own account and
data, and make sure your use complies with the applicable service terms and
local law.

Never commit `cookies.txt`, `.env`, manifests, logs, or runtime state. They are
already ignored by the included `.gitignore`.

## Requirements

- Linux or macOS
- Python 3.10+
- A valid 115 cookie
- The CID of the remote directory to scan

## Quick Start

```bash
git clone https://github.com/xiaohei210509/115-sync-console.git
cd 115-sync-console

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
```

Edit `.env`, then export it:

```bash
set -a
source .env
set +a
```

Create the runtime directory and cookie file:

```bash
mkdir -p "$SYNC_APP_HOME"
chmod 700 "$SYNC_APP_HOME"
printf '%s\n' 'UID=...; CID=...; SEID=...; KID=...' > "$SYNC_APP_HOME/cookies.txt"
chmod 600 "$SYNC_APP_HOME/cookies.txt"
```

Run a scan:

```bash
.venv/bin/python src/scanner.py
```

Start the downloader:

```bash
.venv/bin/python src/incremental_download.py
```

Start the dashboard:

```bash
.venv/bin/python src/server.py
```

Open `http://127.0.0.1:8090`.

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `SYNC_ROOT_CID` | Remote 115 directory CID | required |
| `SYNC_ROOT_NAME` | Remote root display name | `115` |
| `SYNC_DOWNLOAD_DIR` | Local destination | `~/Downloads/115` |
| `SYNC_APP_HOME` | Runtime state directory | `~/.local/share/115-sync-console` |
| `SYNC_COOKIE_FILE` | Cookie file path | `$SYNC_APP_HOME/cookies.txt` |
| `SYNC_EXCLUDE_PREFIXES` | Comma-separated remote paths to ignore | empty |
| `SYNC_INCLUDE_PREFIX` | Optional remote prefix to include | empty |
| `SYNC_PRIORITY_KEYWORDS` | Comma-separated path keywords downloaded first | empty |
| `SYNC_FILE_WORKERS` | Concurrent files | `4` |
| `SYNC_RANGE_WORKERS` | Concurrent ranges per ranged transfer | `3` |
| `SYNC_PART_CHUNK_MIB` | Range chunk size | `256` |
| `SYNC_DASHBOARD_HOST` | Dashboard bind address | `127.0.0.1` |
| `SYNC_DASHBOARD_PORT` | Dashboard port | `8090` |
| `SYNC_ADMIN_TOKEN` | Token for cookie and sync write APIs | empty |

Excluded paths are matched against full remote paths, including
`SYNC_ROOT_NAME`. For example:

```dotenv
SYNC_ROOT_NAME=Media
SYNC_EXCLUDE_PREFIXES=Media/Downloads,Media/Cache
```

## Dashboard API

- `GET /api/status`: live dashboard state
- `GET /api/cookie`: force a cookie health check
- `POST /api/cookie`: replace the cookie and restart the downloader
- `POST /api/sync`: start differential sync; use `{"rescan": true}` to scan first

When `SYNC_ADMIN_TOKEN` is set, POST requests must include:

```http
X-Admin-Token: your-token
```

The dashboard stores the token only in the browser's local storage.

## Reverse Proxy

The dashboard defaults to `127.0.0.1`. Keep it private or put it behind an
authenticated reverse proxy. If you expose it publicly, always set a strong
`SYNC_ADMIN_TOKEN` and protect the site itself with access control.

## systemd

Examples are available in [`deploy/systemd`](deploy/systemd). Adjust
`WorkingDirectory`, `EnvironmentFile`, and the service user before installing.

## Project Layout

```text
src/config.py                 Shared environment configuration
src/scanner.py                Recursive 115 directory scanner
src/incremental_download.py   Differential download engine
src/server.py                 Dashboard and control API
assets/sync-bg.png            Dashboard background
deploy/systemd/               Linux service examples
```

## License

MIT
