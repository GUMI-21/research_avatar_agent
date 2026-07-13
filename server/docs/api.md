# Server API

The public API is owned by FastAPI and remains independent of the selected LLM
provider. JSON is encoded as UTF-8.

## Health Check

```http
GET /ping
```

```json
{
  "status": "ok",
  "service": "avatar-agent-server"
}
```

## Chat

```http
POST /api/v1/unity/chat
Content-Type: application/json
```

Request:

```json
{
  "session_id": "unity-demo",
  "message": "Today we completed the first integration."
}
```

`session_id` identifies one conversation and accepts 1 to 128 characters.
`message` is the user input and accepts 1 to 10,000 non-blank characters.

Response:

```json
{
  "request_id": "req_3f887b84e5304fc6b52a7be10ba34b45",
  "reply": "Echo: Today we completed the first integration.",
  "emotion": {
    "label": "neutral",
    "valence": 0.0,
    "arousal": 0.0,
    "intensity": 0.0
  },
  "avatar": {
    "expression": "neutral",
    "action": "idle",
    "intensity": 0.0,
    "duration_ms": 0
  }
}
```

`request_id` correlates logs for one request. `reply` is the assistant text.
`valence` ranges from -1 to 1; `arousal` and both intensity values range from 0
to 1. Supported emotion and expression labels are `neutral`, `happy`, `sad`,
`angry`, `relaxed`, and `surprised`. Supported actions are `idle`, `nod`, and
`wave`. `duration_ms` ranges from 0 to 60,000.

The current implementation is an Echo placeholder with a neutral avatar state.
The response contract is intended to remain unchanged when the LLM and emotion
modules are connected.

Invalid or missing fields return HTTP 422:

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "message"],
      "msg": "Value error, must not be blank",
      "input": "   "
    }
  ]
}
```
