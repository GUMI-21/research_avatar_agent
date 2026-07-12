# Server Logging

The server uses Loguru as its application logging interface. Runtime logs are
written to `/tmp/avatar_agent_log/server.log` by default. The directory is
created automatically when the server starts.

## Usage

Import the shared logger instead of configuring a logger in each module:

```python
from logs import log

log.debug("Loaded project: {}", project_id)
log.info("Server is ready")
log.warning("Memory usage is high")
log.error("Request failed: {}", error)
```

Use `log.exception(...)` inside an exception handler to include the traceback.

## Defaults

| Setting | Default |
| --- | --- |
| Log directory | `/tmp/avatar_agent_log` |
| Log file | `server.log` |
| Level | `DEBUG` in debug, `INFO` in prod |
| Rotation | `10 MB` |
| Retention | `30 days` |
| Compression | `gz` |

Rotated files are renamed by Loguru and compressed automatically. `/tmp` is
appropriate for local development but may be cleaned by the operating system.
A deployed service should configure persistent storage.

## Configuration

Logging is read from the `logging` section of `config/debug.yaml` or
`config/prod.yaml`:

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

The local environment files are ignored by Git. Keep reusable defaults in
`config/config_example.yaml`.

The logging setup also forwards Python standard-library, FastAPI, and Uvicorn
records to the same console and file sinks.

The `/ping` endpoint logs the client IP, HTTP status, and service status.

Run the logging test from the `server/` directory:

```bash
python -m unittest discover -s tests -v
```
