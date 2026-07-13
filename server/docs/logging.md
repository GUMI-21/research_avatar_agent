# Server Logging

The server uses Loguru and writes to `/tmp/avatar_agent_log/server.log` by
default. The directory is created automatically.

## Usage

```python
from logs import log

log.debug("Loaded project: {}", project_id)
log.info("Server is ready")
log.exception("Request failed")
```

## Configuration

Logging is configured in `config/debug.yaml` or `config/prod.yaml`:

```yaml
logging:
  level: DEBUG
  directory: /tmp/avatar_agent_log
  file_name: server.log
  rotation: 10 MB
  retention: 30 days
  compression: gz
  console: true
```

Debug uses `DEBUG`; prod uses `INFO`. Logs rotate at 10 MB, are compressed with
gzip, and are retained for 30 days. Standard Python, FastAPI, and Uvicorn records
are forwarded to the same console and file outputs.

Run the test from `server/`:

```bash
python -m unittest discover -s tests -v
```
