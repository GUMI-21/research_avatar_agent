"""Conservative shortcuts for messages that require no retrieval or tools."""


def is_simple_greeting(message: str) -> bool:
    # Only whole-message greetings qualify; a greeting plus a task must still use tools.
    return message.strip().strip("。！!，, \t\r\n") in {"你好", "您好", "嗨"}
