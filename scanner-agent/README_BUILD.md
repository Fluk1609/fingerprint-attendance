# Scanner Agent (Windows)

This folder is the single source for the local scanner process. `agent.py` contains the existing enrollment/check-in API logic moved from `backend/scanner.py`; `zk9500_driver.py` preserves the earlier standalone driver class for reference.

## Configuration
1. Copy `config/scanner.env.example` to `config/.env`.
2. Set `CLOUD_API_URL`, `SCANNER_AGENT_TOKEN`, and a strong random `LOCAL_PAIRING_CODE`.
3. Keep `config/.env` private and out of Git.

## Run from Python for initial testing
Use 64-bit Python 3.10 and install `requirements.txt`, then run `python agent.py`. The server binds only to `127.0.0.1:5001`.

## Pairing API
`POST http://127.0.0.1:5001/api/scanner/pair` with JSON `{"code": "..."}` returns a short-lived session token. Subsequent `/api/scanner/*` calls must send `X-Scanner-Session`. The frontend has not yet been changed to use this flow; do not deploy this intermediate patch as a completed system.

## Build status
PyInstaller `.spec` is intentionally not generated yet. First validate `pyzkfp`/pythonnet and all ZKTeco native DLL dependencies on the target Windows environment. Build the first release as One-Folder, not One-File.
