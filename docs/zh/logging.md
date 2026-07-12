# Server 日志

Server 使用 Loguru 作为统一的应用日志接口。运行日志默认写入
`/tmp/avatar_agent_log/server.log`，服务启动时会自动创建该目录。

## 使用方法

业务模块统一导入共享日志对象，不要在各模块中重复配置 logger：

```python
from logs import log

log.debug("Loaded project: {}", project_id)
log.info("Server is ready")
log.warning("Memory usage is high")
log.error("Request failed: {}", error)
```

在异常处理代码中使用 `log.exception(...)`，可以同时记录异常堆栈。

## 默认配置

| 配置 | 默认值 |
| --- | --- |
| 日志目录 | `/tmp/avatar_agent_log` |
| 日志文件 | `server.log` |
| 日志级别 | debug 为 `DEBUG`，prod 为 `INFO` |
| 文件轮转阈值 | `10 MB` |
| 保留时间 | `30 days` |
| 压缩格式 | `gz` |

达到轮转阈值后，Loguru 会自动重命名并压缩旧日志。`/tmp` 适合本地开发，
但操作系统可能会清理其中的文件；正式部署时应配置持久化目录。

## 配置文件

日志配置从 `config/debug.yaml` 或 `config/prod.yaml` 的 `logging` 部分读取：

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

本地环境配置文件由 Git 忽略，可复用的默认结构保存在
`config/config_example.yaml`。

日志初始化还会将 Python 标准库、FastAPI 和 Uvicorn 的日志转发到相同的
控制台和文件输出目标。

`/ping` 接口会记录客户端 IP、HTTP 状态码和服务状态。

在 `server/` 目录运行日志测试：

```bash
python -m unittest discover -s tests -v
```
