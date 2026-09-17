# 2026-08-25 面试复盘：Runtime Registry 与 Session

## 1. 为什么需要 Runtime Adapter 和 Runtime Registry？

Personal Agent、Codex、Claude Code 和 DeepSeek Harness 的启动方式、输入格式和输出事件都不同。Adapter 把这些差异转换成统一的 `stream(RuntimeRequest) -> RuntimeEvent` 接口，编排层不需要包含大量厂商 `if/elif`。

Registry 本质是带校验的 `runtime_id -> RuntimeFactory` 字典。数据库只保存 `native`、`codex` 这类稳定标识，运行时再通过 Registry 创建对应 Adapter。新增实现只注册 Factory，不修改 Agent 核心流程。

## 2. 为什么 Registry 保存 Factory，而不是保存 Adapter 实例？

保存实例会让多个 Session 共享同一个对象，Adapter 内的取消状态、子进程句柄或临时上下文可能串到其他请求。Factory 保存的是“如何创建”，每次 Run 可以获得独立实例。

Factory 还可以通过闭包注入依赖：

```python
registry.register("native", lambda: NativeAdapter(llm_runtime))
```

代价是每次创建对象有少量开销；如果某个 Adapter 明确无状态且创建成本高，可以以后调整生命周期，而不是默认全局共享。

## 3. Python `Protocol` 与 Go `interface` 有什么关系？

`Protocol` 支持结构化子类型：具体类不必显式继承接口，只要提供兼容的方法签名，就能通过静态类型检查。这与 Go 的隐式接口实现接近。

```python
class AgentRuntimeAdapter(Protocol):
    async def stream(self, request: RuntimeRequest) -> AsyncIterator[RuntimeEvent]: ...
```

末尾 `...` 只表示这里声明协议，不提供实现。Python 官方文档将这种机制称为 structural subtyping，也可以理解为带静态检查的 duck typing。[Python typing 文档](https://docs.python.org/3/library/typing.html#typing.Protocol)

## 4. 为什么所有 Runtime 都要输出统一的 `RuntimeEvent`？

WebSocket、日志、测试、未来 Unity 适配层都只消费统一事件，例如 `run_started`、`assistant_delta`、`tool_completed` 和 `run_failed`。厂商专有事件在 Adapter 边界完成归一化，避免协议细节向上泄漏。

统一事件不等于展示模型隐藏思维链。系统只展示可审计状态、工具调用、检索结果、handoff 和用量；原始 chain-of-thought 不保存、不转发。

## 5. `RuntimeRequest` 为什么使用 `@dataclass(frozen=True)`？

`dataclass` 自动生成构造、比较和显示方法；`frozen=True` 阻止正常代码重新赋值字段，降低请求在多个组件间传递时被意外修改的风险。

这是浅层不可变：如果字段内部是可变字典，字典内容仍可能变化。因此不可变事件结构后续应优先使用不可变值，或在边界复制 payload。

## 6. `SessionRecord` 和 SQLAlchemy `AsyncSession` 有什么区别？

- `SessionRecord` 是业务实体：一个用户对话框，长期保存在 `sessions` 表。
- `AsyncSession` 是数据库工作单元：通常在一次 HTTP 请求中执行查询、事务和对象跟踪，请求结束后关闭。

一个 `SessionRecord` 会长期关联多条 Message；一个 `AsyncSession` 只在一次短生命周期数据库操作中使用。命名相同，但一个属于业务域，一个属于持久化基础设施。

## 7. 为什么每个 HTTP 请求注入独立的 `AsyncSession`？

每个请求独立管理事务，能够明确地 `commit()` 或 `rollback()`，避免不同并发请求共享 ORM 状态。FastAPI 通过 `Annotated[AsyncSession, Depends(get_db_session)]` 调用依赖函数，将 `yield` 的对象注入路由，并在请求结束后执行清理代码。[FastAPI Depends 文档](https://fastapi.tiangolo.com/tutorial/dependencies/)、[yield 依赖文档](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/)

这不代表每个请求都新建物理连接。`AsyncSession` 执行 SQL 时从 Engine 获取连接，事务结束后连接归还连接池。

## 8. Engine、Connection Pool 和 AsyncSession 的关系是什么？

```text
全局 Engine
  -> 管理数据库驱动和连接池
  -> AsyncSession 按需借 Connection
  -> commit/rollback 后归还 Connection
```

应用通常为一个数据库保留一个 Engine，而不是每个请求创建 Engine。SQLAlchemy 官方说明，Session 在需要访问数据库时向 Engine 获取连接，事务结束后将底层连接释放回连接池。[SQLAlchemy Session Basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)、[Engine 配置](https://docs.sqlalchemy.org/en/20/core/engines.html#pooling)

## 9. `flush()`、`commit()` 和 `rollback()` 分别做什么？

- `flush()`：把内存中的新增或修改转换成 SQL 并发送到当前事务，但尚未永久提交。
- `commit()`：先执行必要的 flush，再提交事务，使修改生效。
- `rollback()`：撤销当前事务，并让发生数据库错误后的 Session 恢复为可继续管理的状态。

项目让 Repository 负责 `add/flush`，API 负责 `commit/rollback`，因为一次 HTTP 操作的事务边界属于应用层。SQLAlchemy 官方将 Session 描述为 unit of work，并说明 `commit()` 会无条件先 flush。[SQLAlchemy Session Basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html#committing)

## 10. 为什么 Agent 重名返回 409，并且捕获 `IntegrityError`？

数据库使用 `UniqueConstraint(client_id, name)` 保证同一客户端内 Agent 名称唯一。并发请求即使都通过应用层预检查，最终仍可能同时写入，因此数据库约束才是最终一致性保障。

`IntegrityError` 是 SQLAlchemy 对唯一键、外键和非空约束等完整性错误的统一封装。当前接口捕获后回滚并返回 409 Conflict。更完善时应检查具体 constraint 名称，避免把其他完整性错误误报成“名称重复”。

## 11. Session 的客户端隔离如何实现？

所有 Repository 查询同时包含 `client_id` 和资源 ID：

```python
SessionRecord.client_id == client_id,
SessionRecord.id == session_id,
```

创建 Session 前，还要验证 `agent_id` 对应的 Agent 属于同一客户端。不能只按主键查询后再在 Python 中检查，因为新接口很容易漏掉检查，而且不必要的数据已经从数据库取出。

属于其他客户端与真正不存在统一返回 404，避免通过响应差异判断资源是否存在。

## 12. 为什么 `sessions` 表同时保存 `client_id` 和 `agent_id`？

仅通过 `agent_id` JOIN 也能推导 Client，但直接保存 `client_id` 可以让所有查询天然带租户范围，简化索引、隔离测试以及未来按客户端归档或删除数据。

代价是存在冗余，需要在创建时验证 Session 和 Agent 的 `client_id` 一致。当前 Repository 已执行该验证；更强的数据库方案可以增加复合外键，但会提高迁移复杂度。

## 13. Pydantic Schema 为什么与 SQLAlchemy Model 分开？

SQLAlchemy Model 表达数据库结构，Pydantic Schema 表达外部 API 合约。分离后可以避免数据库新增内部字段时自动暴露给客户端，也可以分别设置请求校验与响应格式。

`SessionRead.model_validate(record)` 按同名字段提取并校验数据；`ConfigDict(from_attributes=True)` 允许 Pydantic 从 ORM 对象属性读取，而不只接受字典。[Pydantic arbitrary class instances](https://docs.pydantic.dev/latest/concepts/models/#arbitrary-class-instances)

## 14. 为什么 `client_id` 不放在 `SessionCreate` 请求体？

资源归属必须来自可信边界，例如本地演示阶段的 `X-Client-ID`，未来替换为认证 Token。若请求体允许传 `client_id`，调用者可以尝试伪造其他客户端的资源归属。

因此请求体只包含业务输入 `agent_id` 和 `title`，API 通过依赖注入获得客户端范围，再传给 Repository。

## 15. Alembic 迁移文件解决了什么问题？

修改 ORM 类不会自动修改已有数据库。Alembic 用有序 revision 记录数据库结构演进：`upgrade()` 创建或修改结构，`downgrade()` 提供回退路径，`down_revision` 串联迁移顺序。

测试运行 `upgrade head`、模型差异检查和 `downgrade`，能够发现“代码模型已经改变，但迁移遗漏”的问题。Alembic 官方将其定义为基于 SQLAlchemy 的关系数据库变更管理工具。[Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)

## 16. 为什么当前选择 SQLite，未来能否迁移 MySQL？

SQLite 没有独立数据库服务进程，应用直接读写本地数据库文件，适合本地优先、个位数客户端和低部署成本的演示系统。[SQLite Serverless](https://www.sqlite.org/serverless.html)、[SQLite 使用场景](https://www.sqlite.org/whentouse.html)

Repository 和业务层依赖 SQLAlchemy，而不是 SQLite 专有 API；当前 `String`、`Text`、`ForeignKey` 和 `Index` 等结构也较通用。迁移 MySQL 时主要更换异步驱动和 URL，并重新验证外键、时间类型、排序规则、JSON/全文检索和并发事务语义。

SQLite 能满足当前目标，但不适合多台应用服务器直接共享同一个网络文件，也不适合高写并发场景。达到这些条件时应切换 MySQL 或 PostgreSQL，而不是继续给 SQLite 增加分布式补丁。

## 快速自测

面试前应能在不看代码的情况下回答：

1. `runtime_id -> RuntimeFactory` 为什么比 `runtime_id -> Adapter实例` 更安全？
2. `SessionRecord`、`AsyncSession`、Engine 和 Connection 分别是什么？
3. 为什么 `flush()` 后仍需要 `commit()`？
4. 为什么租户查询必须在 SQL 条件中包含 `client_id`？
5. 为什么请求 Schema、响应 Schema 和 ORM Model 不复用一个类？
6. 当前 SQLite 的适用边界是什么，迁移 MySQL 要验证哪些差异？
