# Avatar Backend Plan: English-Led Japanese Kana Teaching

## Goal and current state

The goal is English-led gojuon instruction using local Markdown Skill scripts
for demonstrations and guided conversations. Version one is text-only: one
teaching-model call returns both reply and expression suggestions, which the
server validates into semantic Unity controls. Speech and independent emotion
modules have replaceable interfaces only, without concrete providers.

The machine is a Mac without Unity Editor. Validate through HTTP, WebSocket and
JSON previews. See the [Workspace roadmap](internship_agent_workspace_plan.md)
for the retained baseline and the [research plan](research_plan.md).

Implemented baseline:

- courses/gojuon-en/SKILL.md: English instructions, hiragana vowels/rows and katakana review.
- CourseSelection: course/lesson IDs and en instruction / ja target language.
- TeachingTurn / AvatarControl: versioned reply/expression validation, neutral/idle defaults.
- SpeechRecognizer, SpeechSynthesizer, EmotionAnalyzer: interfaces without providers or automatic calls.
- CourseCatalog: shared Skill parsing, allowed-root discovery/validation, course/lesson lookup and versioned in-memory snapshots, separately loaded during app creation.
- TeachingSessionRecord / TeachingRepository: one configuration per conversation, storing course/lesson, script hash, completed-turn count and state version; client-scoped creation/lookup with caller-owned transactions.
- Course listing and teaching GET/PUT: bind real courses/lessons to the client's own Native Session and pin the script hash; identical retries are idempotent, while rebinding/upgrades are rejected for now.
- TeachingService.prepare: internal request preparation rechecks binding/Native/script hash, adds bounded course context and preserves conversation/memory/RAG fields; Native and LangGraph enforce no tools/handoff.
- TeachingTurnParser and internal Native teaching mode: buffer/validate joint JSON, emit reply only, fall back to neutral for invalid avatar and attach validated teaching metadata to completion without an extra model call.
- Teaching WebSocket execution: bound Sessions reuse preparation, Native/LangGraph, Message/Run/events; an app-scoped SessionRunGuard rejects concurrent scoped Runs and binding PUTs during execution.

HTTP teaching chat, automatic progress updates and Unity playback are not implemented.
Courses can be queried/selected through the API but are not automatically Agent Skills
and are now injected for bound Session Runs. RunExecutionService/WebSocket select teaching
from the binding; unbound Sessions retain the Workspace path. HTTP /avatar/chat comes next,
reusing the execution service and guard. Live-model teaching quality still needs separate acceptance.

## 1. Experience and scope

Start with あ/い/う/え/お, continue through hiragana rows and then katakana pairing.
Dakuten, combined kana, grammar and listening/speaking assessment are deferred.

Use short explanation → demonstration → one question → wait → hint/feedback/review.
Scripts guide teaching; the server controls selected lessons and confirmed
progress. Showing a character is not evidence of mastery. Text feedback must not
claim to hear pronunciation, assess handwriting or measure the student's feelings.

| Stage | Deliverable | Acceptance |
| --- | --- | --- |
| A: course text | Discover/bind courses, reuse Native, multi-turn English guidance | Course/lesson versions, context, client scope, messages/Runs |
| B: expression controls | Same-call expression parsing, mapping, durable events and JSON preview | Bounds, neutral fallback, cancellation, expiration/deduplication |
| C: closeout | Failure regression, Mac demo, Unity handoff | Repeatable text teaching, Usage/latency, contracts and limitations |

Unity C#, scenes, speech services, separate emotion models, a lesson-editor UI and
participant studies are out of scope. Preserve legacy Unity and Workspace;
live Google-account validation remains deferred.

## 2. Local course directory

    courses/
      gojuon-en/
        SKILL.md

Use YAML frontmatter and Markdown compatible with SkillCatalog. name is course_id.
Metadata includes display name, instruction_language=en, target_language=ja,
lesson_ids, scenarios and empty recommended_tools. Matching headings identify lessons such as
hiragana-vowels.

- CourseCatalog reuses Skill parsing and validates language, lessons, size and version. Retained internal metadata does not change public Skill API fields.
- courses is project teaching content, not a global Codex Skill installation or automatic enablement for all Workspace Agents.
- Accept IDs only and resolve under administrator-approved roots; reject traversal, symlink escapes and arbitrary file reads.
- Selectable lessons must be declared and match exactly one unindented level-two heading (## lesson-id) outside code fences; support headings cannot be selected.
- CourseSelection validates format and CourseCatalog.resolve rejects missing courses/lessons; TeachingService uses this check for initial binding.
- Immutable course snapshots and bounded reads are implemented. Refresh replaces the complete catalog only after validation; failure retains the old catalog.
- Original-byte hashes accompany content; edits require explicit refresh. Per-Run version pinning/progress migration still belong to later teaching-execution batches.
- Courses are public administrator-provided material. Student messages/state remain client-scoped.
- Skills cannot grant tools or override server output schemas.

Kana/romaji were checked against the [MEXT chart](https://www.nihongo-ews.mext.go.jp/contents_files/download/?cfid=106&content_id=421)
and [Japan Foundation resources](https://www.erin.jpf.go.jp/en/extra/syllabary/).
Teaching prompts and sequence are project-authored.

## 3. Architecture

    Avatar API → CourseCatalog / TeachingService → existing RunExecutionService
      → course snapshot, recent dialogue, existing memory/RAG → Native / LangGraph
      → one LLM response {reply, avatar}
      → TeachingTurnParser → validation/mapping → persist result/progress
      → assistant_delta (reply only), avatar_control → final Run event

- CourseCatalog owns scripts, lessons and versions, not conversation execution.
- TeachingService owns binding/lesson/progress; Repository queries and Service transactions remain separate.
- Reuse runtime=native, not a duplicate teaching Runtime.
- TeachingTurnParser validates output and falls back for invalid expressions; current semantics use AvatarControl bounds, and future presentation policy does not assess student psychology.
- Disable teaching tools/automatic handoff initially and reject unauthorized calls at execution too.
- Retain LangGraph orchestration; ordinary Workspace does not enable teaching completion.
- Do not automatically write progress/guessed affect into Agent memory. Lessons cannot bypass permissions.

### Implemented internal request preparation

TeachingService.prepare accepts an internal RuntimeRequest, not a client-selected mode.
It rechecks client-scoped teaching state/Session, current Agent identity and Native runtime,
rejecting a different target Agent. It resolves the course/lesson and checks the bound hash;
removed or changed scripts are rejected, not silently upgraded.
The complete course body and server-selected lesson, script/state version and committed-turn
count form a preparation section capped at 8,000 characters. Reject over-budget scripts rather
than truncate an output contract. This caps the course section, not total request tokens.
The complete script is sent with the selected lesson identified; actual teaching quality and
instruction following still need separate live-model acceptance.

The copied request uses mode=teaching and no handoff candidates while preserving conversation,
memory, RAG and model fields. Existing assembly owns their scope and individual budgets.
Preparation does not call a model, create Run/Message records or update progress.
Native offers no tools and rejects unsolicited tool/delegation calls; greetings keep teaching
instructions. LangGraph rejects both manual and runtime-requested handoffs without executing
the target. Workspace defaults to mode=workspace and retains existing behavior.
RunExecutionService prepares teaching before creating a Run or user Message, rejecting
unavailable/changed scripts or a different/non-Native target early. Teaching does not load
other Agents' runtime contexts or Workspace Agent Skills; it preserves the bound Agent's
recent conversation, memory and RAG with separate course instructions.

### Implemented joint parsing and text transport

TeachingTurn is complete JSON. Internal Native teaching mode buffers at most 65,536
raw characters including escaping/whitespace, rejecting overflow instead of streaming
partial teaching text. First validate the object/version/top-level fields and nonblank
reply (at most 10,000 characters), then avatar. Invalid avatar alone preserves reply
and replaces the complete control with neutral/idle and zero intensity/duration,
with reason invalid_avatar. Missing/partial avatar uses contract defaults without a
fallback; explicit null/invalid values trigger fallback.
Reject malformed/duplicate-key JSON, nonstandard NaN/Infinity, extra top-level fields,
invalid replies/versions, Markdown fences or explanatory wrappers; do not salvage fragments.

Success emits one assistant_delta containing only the validated reply. run_finished.payload.teaching
contains output version, validated avatar and fallback_reason, not duplicate reply or invalid raw
parameters. This metadata is not an executable avatar_control command. Presentation tables,
command IDs/expiry and Unity playback remain planned; progress is unchanged.
Provider/validation failure discards buffered text without a success terminal; cancellation
propagates. If provider information was received before failure, emit existing usage status
(reported when available, otherwise unavailable) without retrying or adding model calls.
Errors/fallback logs expose only safe reasons/types, not raw JSON or Pydantic input details.
Workspace incremental streaming is unchanged; incremental teaching JSON parsing is deferred.

### Implemented WebSocket bridge and Session guard

Bind a course using PUT, then send the existing send_message (session_id/content) to
/api/v1/ws?client_id=...; there is no new WS command or client-selected mode. The binding
selects teaching; Message stores plain reply and completion events persist presentation
metadata. Separate presentation tables and progress commits remain planned.
The app-scoped guard claims (client_id, session_id) and rejects busy requests immediately
instead of queueing stale messages. All production WS Session Runs share it, as do binding
PUTs. Cross-connection conflicts return session_busy; same-connection tasks retain
run_in_progress. Preparation failures return not_found or teaching_conflict. Bound Sessions
without a catalog/shared guard fail closed rather than reverting to ordinary chat;
binding PUT returns 503 if the shared guard is missing.

Success, failure, cancellation and early consumer close close inner graph iterators and
release ownership. Disconnect cleanup shields against repeated outer cancellation and
awaits task cleanup. Early close records a cancelled terminal; interrupted database work
is rolled back before cancellation state is written, without assistant/progress writes.
This is single-process, single-event-loop memory ownership, not a distributed lock or
cross-process recovery. Use one Server worker for this demo. Local cancellation does not
guarantee upstream billing stops. HTTP wiring follows in the next sub-batch and will share the guard.

## 4. First-batch contracts

| Contract | Implemented fields/bounds |
| --- | --- |
| CourseSelection | Default course_id=gojuon-en, lesson_id=hiragana-vowels; en/ja languages; extra fields rejected |
| TeachingTurn | schema_version=1; nonblank reply up to 10,000 characters; neutral avatar default |
| AvatarControl | Existing expression/action semantics; finite intensity in [0,1], integer duration_ms in [0,60000]; extras rejected |
| SynthesizedSpeech | Internal future TTS audio bytes/media_type |
| Optional ports | ASR transcribe, TTS synthesize, EmotionAnalyzer analyze; explicit language, no implementation |

Retain neutral/happy/sad/angry/relaxed/surprised and idle/nod/wave. Policies can
use a smaller neutral/happy/gentle-nod subset. These are tutor presentation
suggestions, not student emotion recognition. Intensity is not a PAD/VAD third
dimension; valence/arousal or confidence estimates are not required.

Example, also included in the course:

    {"schema_version":1,"reply":"That's right! い is i. Which character is u?","avatar":{"expression":"happy","action":"nod","intensity":0.35,"duration_ms":800}}

Optional modules can later be injected; they are not registered/called by default
and require no current keys. EmotionAnalyzer returns the existing EmotionState;
a future policy decides whether to use it. No arbitrary client code, additional
model calls, audio storage or service dependencies are introduced for these ports.

## 5. Resources/APIs

Reuse Agent, Session, Message, Run and RunEvent, filtering persistent resources
by client_id plus IDs.

- Implemented GET /api/v1/avatar/courses: allowed-course/lesson metadata, excluding script bodies, internal metadata and server paths.
- Implemented GET/PUT /api/v1/avatar/sessions/{session_id}/teaching: read or initially bind a course/lesson; an empty PUT object selects default vowels, with the version set by the server.
- Planned POST /api/v1/avatar/chat: text teaching for a bound Native Session; reply, Run and presentation.
- Implemented reuse of /api/v1/ws?client_id=... to resolve teaching behavior from Session configuration.
- Planned POST /api/v1/avatar/preview: validate/map suggestions without model calls or Session mutation.
- Planned GET /api/v1/avatar/runs/{run_id}/presentation: persisted output.

Retain X-Client-ID/WS scope, not authentication; the course list is shared public administrator metadata.
Missing configurations/resources, cross-client access and unavailable courses/lessons return 404;
non-Native binding returns 409, invalid input 422. Identical course/lesson/hash PUTs preserve
progress, version and timestamps. Lesson changes or script upgrades return 409 until Run guards
and version migration are implemented. Stored configurations remain readable after catalog
removal for audit, but PUT still validates the catalog; old script execution is not guaranteed.
Legacy POST /api/v1/unity/chat remains unchanged; Unity must explicitly migrate
to the new pipeline rather than silently changing its neutral/idle behavior.

The teaching_session_states extension table now uses session_id as its primary
and foreign key, allowing one configuration per conversation. completed_turns
starts at 0 and counts committed turns, not mastery; state_version starts at 1
for future optimistic updates. Progress updates and optimistic state-version checks are not implemented.
course_version stores the script SHA256 at binding time, not an archived script.
Binding and each WS execution validate course/Native and the bound script version before execution.
Repository methods only flush; Service commits/rolls back and logs successful commits.
Primary-key conflicts return 409 so callers can retry.
The Run-presentation table remains planned for suggestions, controls, fallback
and latency. Do not duplicate chat or write per-frame records.
Courses are read-only to conversations.

## 6. Correctness

- **Language/quality:** require English explanations while allowing Japanese/romaji. Language metadata validation is not proof of output quality; live-model acceptance is separate.
- **Joint generation:** reply/expressions share one call and existing Provider Usage, with no mandatory second affect charge.
- **Parsing/fallback:** validate usable reply first. Invalid avatar alone preserves reply with a logged neutral fallback. Broken JSON/missing or blank reply/generation failures fail rather than fabricate teaching. Native parsing is wired to teaching WS; HTTP wiring follows.
- **Terminal order:** commit presentation/progress before the unique run_finished; retain the ordinary Workspace path.
- **Cancellation/concurrency:** share an active-Run guard across teaching HTTP/WS. Cancellation stops remaining work without committing valid new commands/completed progress; stale snapshots cannot overwrite newer state.
- **Replay:** planned avatar_control has command_id and expiration. Restore state without repeating expired one-shot actions; Unity behavior still needs live acceptance.
- **Data/permissions:** lessons, answers and suggestions cannot expand permissions. No hidden chain of thought, secrets or full sensitive content in ordinary logs.
- **Traceability:** course/lesson/hash, output version, model, Usage status, latency and fallback. Report engineering, live teaching and Unity acceptance separately.

## 7. Batches

Target roughly 100 functional lines per batch, excluding tests, repeated
declarations, comments/docs. Split further when necessary, without calendar dates.
Each backend batch runs appropriate tests/full unittest and pauses for review.

| Batch | Complete change | Areas | Acceptance |
| --- | --- | --- | --- |
| 1 (implemented) | Course seed, selection/reply/expression contracts, optional ports | courses/, schemas/, adapters/avatar/ | Real script parsing, valid example, bounds, legacy compatibility |
| 2 (implemented) | CourseCatalog/lesson discovery and root settings | services/courses.py, core/settings.py | Roots, language/lessons, size, version, escape rejection |
| 3 (implemented) | Teaching state/model/migration/Repository | models/, migrations/, repositories/ | Client scope, Session binding, course version, progress defaults and rollback |
| 4 (implemented) | Course lookup and initial teaching-binding REST | services/teaching.py, api/ | Real course selection, Native binding, client isolation, idempotency/conflicts; rebinding/upgrades deferred |
| 5 (implemented) | Internal teaching request/context/policy preparation | services/teaching.py, adapters/agent/, orchestration/ | Course budget/version, preserved memory/RAG, no tools/handoff, Workspace regression; public wiring deferred |
| 6 (implemented) | Joint-output parser/plain reply/fallback | services/teaching_output.py, adapters/agent/native.py | No raw JSON leakage, invalid-avatar fallback, bad-reply failure, buffer bounds and retained Usage |
| 7A (current) | WS teaching bridge/shared Session guard | services/run_execution.py, services/session_run_guard.py, api/ | Multi-turn, binding selection, cross-connection/binding conflicts, preflight, cancel/disconnect cleanup |
| 7B | HTTP Native bridge | schemas/, api/routes/teaching.py | Same WS execution/guard, HTTP/WS busy protection, Message/Run; A |
| 8 | Presentation persistence/pre-terminal commits | models/, repositories/, services/ | One result/turn, snapshot versions, no cancelled progress |
| 9 | Avatar events/query/preview | schemas/run_stream.py, services/run_event.py, api/ | Fields, expiration, durable replay, deduplication contract |
| 10 | Client event compatibility/stream integration | web/src/shared/api/, server/app/ | Reply-only teaching, ordinary chat unchanged; B |
| 11 | Failure/cancel/disconnect/Usage regression | tests/, necessary Service fixes | Terminal correctness, no duplicate cost/state/actions, unused ports harmless |
| 12 | Mac text demo/Unity handoff | server/scripts/, server/docs/, bilingual docs | Public course, dialogue fixtures, controls, explicit Unity acceptance; C |

Speech and separate emotion Providers are not implemented in these batches.
Split batch ten into reviewable backend/frontend changes as needed.

## 8. Acceptance and limits

The [Server README](../../server/README.md) owns commands: .venv/bin/python on
Mac and .venv/Scripts/python.exe on Windows; migrate before startup and run full
backend unittest per batch. Mock/controlled models verify plumbing, not teaching
accuracy or actual model behavior.

Cases include vowels, correct/incorrect answers, hints/review/pause, lesson
switching, course-version changes, cross-client rejection, invalid JSON/expressions,
cancellation and replay. With real model configuration, separately assess English
explanations, kana/romaji accuracy, one question at a time and feedback.

Without Unity, compilation, scenes, UniVRM APIs, actual expressions, action
stop/deduplication, coordinates, interpolation, naturalness and audio sync remain
unverified. Speech/independent emotion currently have interface acceptance only.
Research/model selection remains in the research plan; presentation parameters
are not measurements of student emotion.
