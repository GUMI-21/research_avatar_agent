# Local teaching courses

Each course lives in `<course-id>/SKILL.md` with YAML frontmatter and Markdown
instructions. The initial `gojuon-en` course teaches Japanese hiragana and
katakana through English text guidance.

The format is compatible with the existing SkillCatalog. Courses are project
resources, not installed Codex Skills. Server app creation loads a separate
CourseCatalog, not the ordinary Agent Skill catalog or model context.

CourseCatalog now validates English/Japanese language metadata, declared lessons,
allowed roots and file size, and exposes immutable content/hash snapshots through
internal list/get/resolve methods. Explicit refresh replaces the catalog only
after all files validate. Failed refresh retains the previous snapshot.
Session binding, teaching generation and public course APIs are not available yet.

Declare selectable lessons in metadata.lesson_ids with matching unindented
level-two headings (## lesson-id) outside code fences. Keep supporting sections
such as teaching behavior and output format separate. The course catalog
explicitly validates lesson IDs instead of treating every Markdown heading
as a lesson. Scripts describe instruction only and cannot grant tools or change
server validation and approval policies.

Plans: [中文](../docs/zh/avatar_integration_plan.md) ·
[English](../docs/en/avatar_integration_plan.md).
