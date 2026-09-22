"""Safe runtime policy exposed to workspace clients."""

from typing import Literal

from pydantic import BaseModel


class RuntimePolicyResponse(BaseModel):
    demo_mode: bool
    blocked_tool_risks: tuple[
        Literal["read_only", "local_write", "external_read", "external_write"],
        ...,
    ]
