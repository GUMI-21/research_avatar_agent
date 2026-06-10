# Emotion-Aware Pedagogical Avatar Agent

This repository is for a master's research and portfolio project focused on an
emotion-aware 3D pedagogical avatar system.

The goal is to build an AI teaching agent that combines:

- LLM-based tutoring dialogue
- An emotion model for student and teacher state estimation
- Expression and motion generation for a 3D avatar
- Unity/VRM-based avatar rendering
- Evaluation against baseline avatar and real teaching conditions

## Research Theme

Emotion-model-based expression and motion generation for 3D pedagogical avatars,
and its impact on learning experience.

## Planned Architecture

1. Student input through text or speech
2. AI tutoring agent generates teaching responses
3. Emotion model estimates student state and teacher affective response
4. Expression and motion planner outputs avatar control JSON
5. Unity client renders facial expressions, gaze, nodding, gestures, and voice

## Initial Technical Direction

- Agent framework: OpenAI Agents SDK for the first prototype, LangGraph for
  stateful workflow experiments
- Backend: Python for rapid AI prototyping, with possible Go services for
  production-style APIs and realtime infrastructure
- Avatar client: Unity with VRM models
- Emotion model: PAD/VAD-based representation, assisted by LLM-based state
  estimation

