# Local teaching courses

Each course lives in `<course-id>/SKILL.md` with YAML frontmatter and Markdown
instructions. The initial `gojuon-en` course teaches Japanese hiragana and
katakana through English text guidance.

The format is compatible with the existing SkillCatalog. Courses are project
resources, not installed Codex Skills. They are not automatically registered by
the Server's ordinary Skills directory or injected into Workspace conversations.

The first backend batch provides the course fixture and validates its example
against CourseSelection, TeachingTurn and AvatarControl. Runtime course/lesson
discovery, Session binding and teaching generation are planned next; no course
API is available yet.

Declare selectable lessons in metadata.lesson_ids with matching stable headings. Keep supporting sections
such as teaching behavior and output format separate. The future course catalog
will explicitly validate lesson IDs instead of treating every Markdown heading
as a lesson. Scripts describe instruction only and cannot grant tools or change
server validation and approval policies.

Plans: [中文](../docs/zh/avatar_integration_plan.md) ·
[English](../docs/en/avatar_integration_plan.md).
