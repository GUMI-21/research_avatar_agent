"""Tests for the first public chat contract."""

import unittest

from fastapi import FastAPI
from pydantic import ValidationError

from app.adapters.llm import MockLLMAdapter
from app.api.router import api_router
from app.schemas.chat import ChatRequest, EmotionLabel
from app.services.chat import ChatService


class ChatContractTest(unittest.IsolatedAsyncioTestCase):
    """Verify placeholder behavior and public route registration."""

    async def test_placeholder_response_matches_contract(self) -> None:
        response = await ChatService(MockLLMAdapter()).respond(
            ChatRequest(session_id="unity-demo", message="Hello")
        )

        self.assertTrue(response.request_id.startswith("req_"))
        self.assertEqual(response.reply, "Echo: Hello")
        self.assertEqual(response.emotion.label, EmotionLabel.NEUTRAL)
        self.assertEqual(response.avatar.expression, EmotionLabel.NEUTRAL)

    def test_blank_message_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ChatRequest(session_id="unity-demo", message="   ")

    def test_chat_route_is_registered(self) -> None:
        app = FastAPI()
        app.include_router(api_router)
        paths = set(app.openapi()["paths"])
        self.assertIn("/api/v1/unity/chat", paths)
        self.assertIn("/api/v1/llm/config", paths)
