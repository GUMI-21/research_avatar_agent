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

Teaching APIs/state, structured generation and Unity playback are not implemented.
Courses can be queried/resolved internally but are not automatically Agent Skills
or model context. Teaching state models, migrations and Repository come next.

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
- CourseSelection validates format and CourseCatalog.resolve rejects missing courses/lessons. Session binding is not implemented yet.
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
- TeachingTurnParser validates output; AvatarPolicy bounds/maps presentation, not student psychology.
- Disable teaching tools/automatic handoff initially and reject unauthorized calls at execution too.
- Retain LangGraph orchestration; ordinary Workspace does not enable teaching completion.
- Do not automatically write progress/guessed affect into Agent memory. Lessons cannot bypass permissions.

### Initial transport tradeoff

TeachingTurn is complete JSON. First buffer and parse it on the server, then send
plain reply, possibly as one chunk. Progressive word-by-word teaching is not
promised initially. WebSocket still carries lifecycle/final results. Never stream
raw JSON, expression internals or optional-module output into chat. Existing
Workspace streaming stays unchanged; incremental structured parsing can come later.

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

## 5. Planned resources/APIs

Reuse Agent, Session, Message, Run and RunEvent, filtering persistent resources
by client_id plus IDs.

- GET /api/v1/avatar/courses: safe allowed-course/lesson metadata, not absolute paths.
- GET/PUT /api/v1/avatar/sessions/{session_id}/teaching: bind course/lesson and manage teaching configuration.
- POST /api/v1/avatar/chat: text teaching for a bound Native Session; reply, Run and presentation.
- Reuse /api/v1/ws?client_id=... to resolve teaching behavior from Session configuration.
- POST /api/v1/avatar/preview: validate/map suggestions without model calls or Session mutation.
- GET /api/v1/avatar/runs/{run_id}/presentation: persisted output.

These APIs are not implemented. Retain X-Client-ID/WS scope, not authentication.
Legacy POST /api/v1/unity/chat remains unchanged; Unity must explicitly migrate
to the new pipeline rather than silently changing its neutral/idle behavior.

Add teaching-Session and Run-presentation extension tables for course/lesson/hash,
committed progress, suggestions, controls, fallback and latency. Do not duplicate
chat or write per-frame records. Courses are read-only to conversations.

## 6. Correctness

- **Language/quality:** require English explanations while allowing Japanese/romaji. Language metadata validation is not proof of output quality; live-model acceptance is separate.
- **Joint generation:** reply/expressions share one call and existing Provider Usage, with no mandatory second affect charge.
- **Parsing/fallback:** validate usable reply first. Invalid avatar alone preserves reply with a logged neutral fallback. Broken JSON/missing or blank reply/generation failures fail rather than fabricate teaching. Service fallback is implemented in a later parser batch.
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
| 2 (current) | CourseCatalog/lesson discovery and root settings | services/courses.py, core/settings.py | Roots, language/lessons, size, version, escape rejection |
| 3 | Teaching state/model/migration/Repository | models/, migrations/, repositories/ | Client scope, Session binding, versions/progress |
| 4 | Catalog and teaching-binding REST | services/teaching.py, api/ | Course existence, Native binding, cross-client rejection |
| 5 | Teaching options/context/permissions | services/run_execution.py, adapters/agent/ | Budgets, memory/RAG reuse, no tools/handoff, Workspace regression |
| 6 | Joint-output parser/plain reply/fallback | adapters/agent/, services/avatar_policy.py | No raw JSON leakage, bad expressions fall back, bad replies fail |
| 7 | HTTP Native bridge/Session guard | services/teaching.py, api/ | Multi-turn English guidance, busy protection, messages/Runs; A |
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
