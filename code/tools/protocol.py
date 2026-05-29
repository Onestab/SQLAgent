"""MCP协议兼容辅助函数。

本模块用于将当前本地工具实现包装成未来MCP兼容的响应格式。
当前阶段仍由本地函数执行，后续可在此替换为MCP客户端调用。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def mcp_success(data: Any, *, source: str = "local", truncated: bool = False) -> dict[str, Any]:
    return {
        "ok": True,
        "data": data,
        "error": None,
        "meta": {
            "request_id": str(uuid4()),
            "server_time": datetime.now(timezone.utc).isoformat(),
            "truncated": truncated,
            "source": source,
        },
    }


def mcp_error(code: str, message: str, *, retryable: bool = False, source: str = "local") -> dict[str, Any]:
    return {
        "ok": False,
        "data": None,
        "error": {
            "code": code,
            "message": message,
            "retryable": retryable,
        },
        "meta": {
            "request_id": str(uuid4()),
            "source": source,
        },
    }
