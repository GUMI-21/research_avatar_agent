# Avatar 后端开发计划：英语五十音教学

## 当前目标与状态

目标已确定：用英语讲解日语五十音，依据本地 Markdown Skill 脚本进行教学演示及引导式对话。
首版采用文本输入/输出，由教学大模型同一次调用返回回复和表情建议，后端校验后转换为 Unity 可消费的语义参数。
语音和独立情绪模块只预留可替换接口，本阶段不接入实际服务。

当前为 Mac、没有 Unity Editor。通过 HTTP、WebSocket 和 JSON 预览验证后端，真实动画另行验收。
Workspace 工程基线见 [路线图](internship_agent_workspace_plan.md)，研究方向见 [研究计划](research_plan.md)。

已实现基线：

- 仓库根目录 courses/gojuon-en/SKILL.md：英文教学脚本，覆盖平假名元音、其余行及片假名复习。
- CourseSelection：课程/课节 ID、英语讲解和日语学习目标的契约。
- TeachingTurn / AvatarControl：版本化回复与模型表情参数的严格校验，缺省使用 neutral/idle。
- SpeechRecognizer、SpeechSynthesizer、EmotionAnalyzer：协议接口，无实际 Provider 或自动调用。
- CourseCatalog：复用 Skill 解析器，在允许目录发现和校验课程/课节，维护版本化内存快照；Server 创建应用时单独加载课程目录。
- TeachingSessionRecord / TeachingRepository：每个对话一份教学配置，保存课程/课节、脚本哈希、已提交轮数和状态版本；创建/查询按 client_id 隔离，由调用方提交事务。
- 课程列表及教学配置 GET/PUT：仅允许自己的 Native Session 绑定真实课程/课节，固定脚本哈希；同配置重复请求幂等，切课/升级暂拒绝。
- TeachingService.prepare：内部准备教学请求，复核绑定/Native/脚本哈希，注入有预算的课程上下文，保留已有对话/记忆/RAG 字段；Native 与 LangGraph 强制禁止工具和转交。
- TeachingTurnParser 与 Native 内部教学模式：收齐并校验联合 JSON，仅发送纯 reply；表情无效回退中性，完成事件携带校验后的教学结果，不额外调用模型。

尚未实现教学执行 API、自动进度更新或 Unity 播放。
课程已可通过 API 查询和选择，但不自动注册为普通 Agent Skill。
内部请求准备与权限策略已可测试；公开 RunExecutionService/HTTP/WS 尚未接入该准备方法，绑定仍不改变普通聊天处理流程。
下一批桥接教学执行入口及 Session 运行守卫，复用已实现的准备与解析步骤。

## 一、课程体验与首版范围

学习者通过英文对话认识、回忆和练习日语假名。首个演示从 あ/い/う/え/お 开始，
之后按行练习平假名，再进行片假名配对复习；浊音、拗音、语法与听说评测后置。

每轮使用“简短讲解 → 示范 → 一个问题 → 等待回答 → 提示/反馈/复习”的流程。
课程脚本提供教学方法；课节选择和已确认进度由服务端维护，不因模型声称完成而自动认定掌握。
只根据文本回答提供反馈，不声称已听到发音、识别笔迹或测量学生真实情绪。

| 阶段 | 目标 | 验收 |
| --- | --- | --- |
| A：课程文本链 | 发现本地课程、绑定 Session、复用 Native、多轮英文引导 | 课程/课节版本、上下文、client 隔离、消息与 Run |
| B：表情控制链 | 解析同轮模型表情、映射参数、持久事件与 JSON 预览 | 范围校验、中性回退、取消、去重与过期动作规则 |
| C：收口与交接 | 完整异常回归、Mac 演示、后续 Unity 接口说明 | 可重复文本教学、Usage/耗时、协议样例与边界 |

Unity C#、场景、语音服务、独立情绪模型、课程编辑 Web 页面和用户研究均不属于本阶段。
保留旧 Unity API 和普通 Workspace；Google 真实账号联调继续后置。

## 二、本地课程目录

    courses/
      gojuon-en/
        SKILL.md

课程文件使用 YAML frontmatter 和 Markdown 正文，格式兼容现有 SkillCatalog。
name 作为 course_id；metadata 包含展示名、instruction_language=en、target_language=ja、
lesson_ids、适用场景及空 recommended_tools。正文用对应课节 ID 标题组织，例如 hiragana-vowels。

- CourseCatalog 已复用现有 Skill 解析能力，校验课程语言、课节、大小和版本；通用 Skill 元数据仅内部保留，不改变公共 Skill API。
- courses 是项目教学资源目录，不是给 Codex 安装全局 Skill，也不自动加入所有 Workspace Agent。
- 服务端仅接受 ID，通过管理员允许的根目录解析文件；禁止路径穿越、符号链接逃逸及任意文件读取。
- 目录只认可 lesson_ids 声明、且在代码围栏外恰好出现一次的无缩进二级标题（## lesson-id），辅助标题不能被选择。
- CourseSelection 校验 ID 格式；CourseCatalog.resolve 进一步拒绝不存在的课程或课节，TeachingService 在首次绑定时使用该校验。
- 课程对象为不可变快照，读取文件有字节上限；刷新在全部校验成功后原子替换，失败保留旧目录。
- 内容与原始字节哈希一起保存；文件编辑后显式刷新才生效。后续每轮固定版本和进度迁移仍需教学执行批次实现。
- 初版课程为公开的管理员提供内容；学生消息和教学状态仍按 client_id 隔离。
- Skill 只提供教学指令，不扩大工具权限，也不能覆盖服务端输出契约。

字表已参考 [文部科学省假名字表](https://www.nihongo-ews.mext.go.jp/contents_files/download/?cfid=106&content_id=421)
与 [国际交流基金资源](https://www.erin.jpf.go.jp/en/extra/syllabary/) 核对；教学流程和提示为项目自行编写。

## 三、架构与职责

    Avatar API → CourseCatalog / TeachingService → 已有 RunExecutionService
      → 课程快照、近期对话、现有记忆/RAG → Native / LangGraph
      → 同一次 LLM 生成 {reply, avatar}
      → TeachingTurnParser → 校验/映射 → 保存结果与教学状态
      → assistant_delta（仅 reply）、avatar_control → 最终 Run 终态

- CourseCatalog 负责脚本/课节发现和版本，不承担对话执行。
- TeachingService 管课程绑定、当前课节及进度；Repository 管查询，Service 管事务。
- Native/LLM Adapter 负责生成回复；教学继续使用 runtime=native，不新增重复的教学 Runtime。
- TeachingTurnParser 校验结构化输出并回退无效表情；当前沿用 AvatarControl 的语义范围，后续呈现策略不预测学生心理状态。
- 首版教学默认禁用工具及自动 handoff；模型若产生未授权调用，执行边界也必须拒绝。
- LangGraph 保留已有编排职责，普通 Workspace 不启用教学专属完成步骤。
- 不自动把教学进度或模型猜测写入 Agent 长期记忆；课程正文也不能绕过系统权限。

### 已实现的内部请求准备

TeachingService.prepare 接收内部 RuntimeRequest，不对客户端开放执行模式参数。
它按 client_id 复核教学状态与 Session、当前 Agent 身份及 Native runtime，拒绝非绑定 Agent 的目标覆盖；
解析当前课程/课节并核对已存脚本哈希。课程移除或脚本变更时拒绝准备，不自动升级。
完整课程正文连同服务端课节、脚本/状态版本和已提交轮数进入独立准备段，最多 8,000 字符；
超过预算直接拒绝，不截断可能包含输出契约的脚本。预算仅约束该课程段，不是全请求 token 上限。
首版发送整份课程正文并标明选定课节，不声称模型一定遵循教学策略；真实教学质量另行验收。

返回请求使用 mode=teaching，清空 handoff 候选，保留原请求的近期会话、记忆、RAG、模型等字段；
这些上下文仍由既有装配层负责作用域与各自预算。准备阶段不调用模型、不创建 Run/Message、不修改进度。
Native 在教学模式下不提供任何工具定义，并拒绝 Provider 返回的工具/委派调用；问候也保留教学指令。
LangGraph 同时拒绝手动目标转交及 Runtime 发出的转交请求，不执行目标 Agent。
普通 Workspace 默认 mode=workspace，保留现有工具/转交/问候行为。
当前仅可通过内部测试执行此路径；公开运行链尚未桥接准备/解析，不自动启用教学模式。

### 已实现的联合解析与文本传输

TeachingTurn 是一个完整 JSON 对象。Native 内部教学模式缓冲最多 65,536 字符的原始输出（含 JSON 转义及空白），
超限立即拒绝；不逐字显示教学文本。先校验对象、schema_version、顶层字段及非空且最长 10,000 字符的 reply，
再验证 avatar；只有 avatar 非法时保留 reply，并整体回退 neutral/idle、强度和时长为 0，原因 invalid_avatar。
缺省/部分 avatar 使用契约默认值，不算降级；显式 null 或非法值才触发回退。
JSON 损坏、重复键、非标准 NaN/Infinity、额外顶层字段、非法回复或版本均失败，不提取“看似可用”的片段；不修补 Markdown 围栏或混合说明文字。

解析成功只产生一段 assistant_delta，内容为校验后的 reply；run_finished.payload.teaching 携带输出版本、
校验后的 avatar 与 fallback_reason，不包含回复副本或非法原始参数。该元数据不是可执行的 avatar_control 动作命令；
呈现表、command_id/有效期及 Unity 播放仍待后续批次。当前不修改课程进度。
模型失败或校验失败时不转发缓冲内容，不发布成功终态；取消继续向上层传播。
若失败前已收到 Provider 信息，仍发出现有用量状态（有统计则 reported，否则 unavailable），不重试或增加第二次模型调用。
错误/降级只记录安全原因或错误类型，不记录原始 JSON 或 Pydantic 输入详情。
普通 Workspace 的既有逐段流式回复不受影响，教学增量结构化解析可以后续优化。

## 四、已固定的第一批契约

| 契约 | 当前字段与约束 |
| --- | --- |
| CourseSelection | course_id 默认 gojuon-en；lesson_id 默认 hiragana-vowels；instruction_language=en、target_language=ja；拒绝额外字段 |
| TeachingTurn | schema_version=1；非空 reply，最长 10,000 字符；avatar 默认中性控制 |
| AvatarControl | 沿用 AvatarCommand 的 expression/action；intensity 为有限数值且在 [0,1]；duration_ms 为整数且在 [0,60000]；拒绝额外字段 |
| SynthesizedSpeech | 将来语音合成端口返回的音频字节及 media_type，仅内部数据类型 |
| 可选模块协议 | ASR transcribe、TTS synthesize、EmotionAnalyzer analyze；显式传入语言，无具体实现 |

表达沿用 neutral/happy/sad/angry/relaxed/surprised，动作沿用 idle/nod/wave。
实际教学可使用较小集合，例如 neutral、happy 和轻微 nod；这是教师呈现建议，不是学生情绪识别。
强度不代表 PAD/VAD 的第三维；不要求首版输出 valence/arousal 或 confidence 推测。

模型输出示例（课程脚本中同样保留）：

    {"schema_version":1,"reply":"That's right! い is i. Which character is u?","avatar":{"expression":"happy","action":"nod","intensity":0.35,"duration_ms":800}}

语音/独立情绪模块未来通过依赖注入可选接入，默认不注册、不调用，不要求 API Key。
独立情绪接口可返回现有 EmotionState，再由策略决定是否采用；不得直接驱动任意客户端代码。
本阶段不为这些接口增加额外模型请求、音频存储或服务依赖。

## 五、资源与接口

复用现有 Agent、Session、Message、Run、RunEvent；所有持久资源按 client_id 与 ID 过滤。

- 已实现 GET /api/v1/avatar/courses：返回允许课程及课节的安全元数据，不返回脚本正文、内部元数据或服务器绝对路径。
- 已实现 GET/PUT /api/v1/avatar/sessions/{session_id}/teaching：读取或首次绑定 course_id/lesson_id；PUT 空对象使用默认元音课节，课程版本由服务端决定。
- 计划 POST /api/v1/avatar/chat：针对已绑定的 Native Session 执行文本教学，返回 reply、Run 与呈现结果。
- 计划复用 /api/v1/ws?client_id=...：依据 Session 配置进入教学链，避免重复流式服务。
- 计划 POST /api/v1/avatar/preview：只验证和映射表情建议，无模型调用或会话修改。
- 计划 GET /api/v1/avatar/runs/{run_id}/presentation：查询已保存的呈现结果。

REST 沿用 X-Client-ID，WebSocket 沿用现有作用域，仍不是正式认证；课程列表是共享的管理员公开元数据。
无配置、资源不存在、跨客户端访问或课程/课节不可用返回 404；非 Native 绑定返回 409；非法输入返回 422。
相同课程/课节/哈希的重复 PUT 不重置进度、版本或时间；更换课节或脚本哈希返回 409，待运行守卫及版本迁移接好后再开放。
课程目录移除后仍可 GET 已存配置供审计，但 PUT 必须重新通过目录校验；这不代表旧脚本仍可执行。
旧 POST /api/v1/unity/chat 继续兼容；后续 Unity 客户端明确迁移到新链，不自动改变旧 neutral/idle 行为。

已新增 teaching_session_states 教学 Session 扩展表，session_id 同时作为主键和外键，
每个对话最多一份配置。completed_turns 初始为 0，只表示已提交教学轮数，不表示掌握程度；
state_version 初始为 1，为后续乐观并发更新预留，目前尚未实现进度更新或状态版本的乐观并发控制。
course_version 保存绑定时脚本 SHA256，不归档正文；绑定与内部请求准备均校验课程/Native，准备时检查脚本版本；公开运行链尚未接入。
Repository 只 flush，Service 提交/回滚并记录提交成功日志；主键冲突映射为 409，客户端可重试。
Run 呈现表仍待新增，用于保存表情建议、最终控制、降级原因和耗时；不复制聊天全文、不逐帧写库。
课程内容只读，教学对话不通过工具修改服务器脚本。

## 六、运行与验收规则

- **语言与教学质量**：脚本和系统指令约束英语讲解；仍允许展示日语字符和罗马字。
  语言字段的校验不等于保证自然语言输出合格，实际模型质量需单独验收。
- **联合生成**：回复与表情来自同一次 LLM 调用，Usage 使用现有 Provider 报告，不存在默认第二次情绪计费。
- **解析与降级**：先验证可用 reply；只有 avatar 非法时保留回复并回退中性，记录原因。
  整体 JSON 损坏、reply 缺失/空白或生成失败则失败，不伪造教学回答。内部 Native 解析路径已实现；公开教学执行入口仍待桥接。
- **终态**：课程进度与呈现结果完成处理后才发布唯一 run_finished；普通 Workspace 保持原路径。
- **取消与并发**：同教学 Session 的 HTTP/WS 共用活跃 Run 守卫。取消终止剩余工作，
  不提交新的有效动作或已完成进度，过期状态不能覆盖更新版本。
- **补发与动作**：计划增加 avatar_control 扩展事件、command_id 和有效期限。
  事件重放恢复状态展示，不应再次播放过期的一次性动作；Unity 端实现仍需实机验证。
- **数据与权限**：课件、用户回答和模型建议不能扩大权限；不记录隐藏思维链、密钥或完整敏感内容到普通日志。
- **可追溯**：记录课程/课节/脚本与输出版本、模型、Usage 状态、耗时及降级来源。
  工程测试、真实模型教学效果和 Unity 呈现验收分别报告。

## 七、开发批次

每批约 100 行功能代码；测试、重复声明、注释与文档不计入。必要时继续拆分，不设固定日期。
每批必要测试、后端完整 unittest 和 Review 后再进行下一批；以下不是一次性实现清单。

| 批次 | 完整改动 | 主要目录 | 验收 |
| --- | --- | --- | --- |
| 1（已实现） | 课程种子、课程/回复/表情契约、可选模块端口 | courses/、schemas/、adapters/avatar/ | 真实脚本可解析、示例契约一致、参数校验、旧契约兼容 |
| 2（已实现） | CourseCatalog 与课节发现、根目录配置 | services/courses.py、core/settings.py | 允许目录、语言/课节、大小、版本、逃逸拒绝 |
| 3（已实现） | 教学会话扩展模型、迁移、Repository | models/、migrations/、repositories/ | client 隔离、Session 关联、课程版本、进度默认值及事务回滚 |
| 4（已实现） | 课程查询与首次教学绑定 REST | services/teaching.py、api/ | 课程真实存在、Native 绑定、跨客户端拒绝、幂等与冲突；切课/升级后置 |
| 5（已实现） | 内部教学请求准备、脚本上下文与权限约束 | services/teaching.py、adapters/agent/、orchestration/ | 课程预算/版本、保留记忆/RAG、禁止工具/handoff、Workspace 回归；公开执行桥接后置 |
| 6（本批） | 联合输出解析、纯文本提取及表情回退 | services/teaching_output.py、adapters/agent/native.py | 不外泄原始 JSON；非法表情回退、坏回复失败、缓冲上限与已有 Usage 保留 |
| 7 | HTTP Native 桥接与会话守卫 | services/teaching.py、api/ | 多轮英文引导、同 Session 忙碌保护、消息/Run；阶段 A |
| 8 | 呈现持久化与成功终态前状态提交 | models/、repositories/、services/ | 每轮一份、课程快照、状态版本、取消不提交 |
| 9 | Avatar 事件、查询与 JSON 预览 | schemas/run_stream.py、services/run_event.py、api/ | 字段、有效期限、持久补发、去重契约 |
| 10 | 客户端事件兼容与后端流式整合 | web/src/shared/api/、server/app/ | 教学仅显示 reply、普通聊天不变；阶段 B |
| 11 | 错误、取消、断连、用量专项回归 | tests/、必要 Service 小修复 | 完整终态、无重复计费/状态/动作、端口未启用无影响 |
| 12 | Mac 文本教学演示及 Unity 交接 | server/scripts/、server/docs/、中英文文档 | 公开课程、多轮案例、结构化参数、明确待 Unity 验收项；阶段 C |

语音和独立情绪 Provider 不在上述批次中实现；后续有明确需求时再单独规划。
批次 10 如有前后端变化，拆成可独立 Review 的子批次。

## 八、验收环境与后置范围

[Server README](../../server/README.md) 维护命令：Mac 使用 .venv/bin/python，
Windows 使用 .venv/Scripts/python.exe；启动前迁移，每批跑后端完整 unittest。
Mock/可控模型可验证管线，不证明英语教学内容或真实模型的准确性。

后端案例包括：元音入门、正确回答、错误回答重试、请求提示/复习/暂停、切换课节、
课程文件变更的版本处理、跨 client 拒绝、非法模型 JSON/表情、取消和事件补发。
真实模型配置可用后，另外检查英语讲解、假名/罗马字、一次一问和反馈质量。

没有 Unity 时不能验收 Unity 编译、场景绑定、UniVRM API、实际表情、动画去重与停止、
骨骼坐标、插值、自然度及音画同步。语音/独立情绪模块当前只验收接口边界。
用户研究和完整情绪模型选择仍见研究计划，不以模型表情参数代替学生情绪测量。
