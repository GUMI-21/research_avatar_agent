# Research Plan

The backend now targets English-led Japanese gojuon text teaching from local
courses/ Skill scripts. One teaching-model call suggests reply/expressions for
validation and future Unity presentation; see the [backend plan](avatar_integration_plan.md).
Speech and independent emotion models have interfaces only; live Unity and
participant studies are not implemented. See the [Workspace roadmap](internship_agent_workspace_plan.md)
for the retained engineering baseline.

## Core Question

Can an emotion-model-driven 3D pedagogical avatar improve learner engagement,
perceived naturalness, social presence, and learning experience compared with a
non-emotional avatar and real teaching baselines?

## Proposed Research Focus

Instead of building a general LLM avatar demo, this project focuses on an
emotion-aware teaching avatar. The system uses an emotion model to transform
teaching context and student state into facial expressions, gaze, nodding,
gestures, and voice-related behavior.

## Candidate Emotion Models

- PAD/VAD model: useful for continuous expression and motion control
- OCC model: useful for teaching-context appraisal, such as encouragement after
  mistakes or praise after progress
- LLM-assisted estimation: useful for extracting structured affective state from
  dialogue context

Version one validates the teaching model's expression/action suggestions without
a separate emotion-model call. Retain EmotionState and a replaceable analyzer
interface; model selection/evaluation are future research. Presentation intensity
is neither the third PAD/VAD dimension nor a measurement of student emotion.

## Baseline Conditions

- Text-only LLM tutor
- 3D avatar tutor without emotional expression
- Rule-based emotional avatar tutor
- Emotion-model-driven avatar tutor
- Real teacher instruction as a reference condition

## Evaluation Metrics

- Learning gain through pre-test and post-test
- Self-reported understanding
- Engagement and motivation
- Social presence
- Trust and perceived friendliness
- Naturalness of facial expressions and motion
- End-to-end latency and module-level latency

## Portfolio Goal

The implementation should also serve as an AI agent portfolio project. The
system should show tool calling, memory, workflow orchestration, tracing, and
integration with a realtime 3D client.
