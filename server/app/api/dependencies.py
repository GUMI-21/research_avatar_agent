"""FastAPI dependencies shared by public routes."""

from fastapi import Request

from app.services.llm_runtime import LLMRuntime


def get_llm_runtime(request: Request) -> LLMRuntime:
    """Return the application-scoped runtime LLM client."""
    return request.app.state.llm_runtime
