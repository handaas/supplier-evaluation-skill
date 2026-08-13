#!/usr/bin/env python3
"""Multi-MCP client: connects to several HandaaS MCP servers simultaneously.

The supplier-evaluation scenario needs cross-domain data from 6 MCP servers:
  enterprise / enterprise-risk / enterprise-operation / factory-channel /
  factory-insight / recruitment.

This client opens ONE persistent session per server and reuses it across all
tool calls, avoiding the cost of booting each server repeatedly. It mirrors the
atomic skills' transport conventions (streamable-http remote preferred, stdio
local fallback) and never prints secrets — credentials live in each server's
own .env (injected by assets/mcp_server_wrapper.py).

Usage (from compose layer)::

    async with MultiMcpClient() as client:
        score = await client.call("risk", "enterprise_risk_insight_score", {...})
        base  = await client.call("enterprise", "enterprise_get_enterprise_base_info", {...})
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import pathlib
import sys
from typing import Any, Dict, Optional

# --------------------------------------------------------------------------- #
# Server registry: scenario domain key -> upstream MCP server directory
# --------------------------------------------------------------------------- #
SERVER_REGISTRY: Dict[str, str] = {
    "enterprise": "enterprise-mcp-server",
    "risk": "enterprise-risk-mcp-server",
    "operation": "enterprise-operation-mcp-server",
    "channel": "factory-channel-mcp-server",
    "factory": "factory-insight-mcp-server",
    "recruitment": "recruitment-mcp-server",
}

# Per-domain remote-URL env var (falls back to the shared HANDAAS_MCP_URL).
REMOTE_URL_ENV: Dict[str, str] = {
    "enterprise": "ENTERPRISE_MCP_URL",
    "risk": "ENTERPRISE_RISK_MCP_URL",
    "operation": "ENTERPRISE_OPERATION_MCP_URL",
    "channel": "FACTORY_CHANNEL_MCP_URL",
    "factory": "FACTORY_INSIGHT_MCP_URL",
    "recruitment": "RECRUITMENT_MCP_URL",
}


# Skill-level MCP token (shared across all domains in this skill)
SKILL_MCP_TOKEN = "SUPPLIER_EVALUATION_MCP_TOKEN"
class MultiMcpError(RuntimeError):
    pass


# --------------------------------------------------------------------------- #
# Transport resolution
# --------------------------------------------------------------------------- #
def _env(*names: str) -> Optional[str]:
    for name in names:
        val = os.environ.get(name)
        if val and val.strip():
            return val.strip()
    return None


def _is_placeholder(value: str) -> bool:
    text = (value or "").strip().lower()
    return not text or "your_" in text or "example" in text or text in {"todo", "xxx"}


def resolve_server_path(server_dir: str) -> Optional[pathlib.Path]:
    """Locate the upstream server.py for stdio bootstrap."""
    candidates: list[pathlib.Path] = []
    root = _env("HANDAAS_MCP_SERVER_ROOT")
    if root:
        candidates.append(pathlib.Path(root).expanduser() / server_dir / "server" / "mcp_server.py")
    here = pathlib.Path(__file__).resolve()
    for parent in [here.parents[2], pathlib.Path.cwd(), pathlib.Path.cwd().parent, pathlib.Path.home() / "Project"]:
        candidates.append(parent / "handaas-mcp-server" / server_dir / "server" / "mcp_server.py")
    for c in candidates:
        if c and c.exists():
            return c.resolve()
    return None


def get_connection(domain: str) -> Dict[str, Any]:
    """Return how we connect to one domain's MCP (remote preferred)."""
    url = _env(REMOTE_URL_ENV.get(domain, ""), "HANDAAS_MCP_URL")
    if url and not _is_placeholder(url):
        token = _env(REMOTE_URL_ENV.get(domain, "").replace("_MCP_URL", "_MCP_TOKEN"), SKILL_MCP_TOKEN, "HANDAAS_MCP_TOKEN") or ""
        return {"mode": "remote", "url": url, "token": token}
    server_dir = SERVER_REGISTRY.get(domain, "")
    local_path = resolve_server_path(server_dir) if server_dir else None
    if local_path:
        return {"mode": "local", "server_path": str(local_path)}
    return {}


# --------------------------------------------------------------------------- #
# Result extraction (mirrors atomic skills' mcp_client.py)
# --------------------------------------------------------------------------- #
def _plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


def _extract_tool_result(value: Any) -> Any:
    plain = _plain(value)
    if isinstance(plain, dict):
        structured = plain.get("structuredContent") or plain.get("structured_content")
        if structured is not None:
            if isinstance(structured, dict) and set(structured.keys()) == {"result"}:
                return structured["result"]
            return structured
        content = plain.get("content")
        if isinstance(content, list) and content:
            texts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    texts.append(str(item.get("text") or ""))
            text = "\n".join(texts).strip()
            if text:
                try:
                    return __import__("json").loads(text)
                except Exception:
                    return {"text": text}
    return plain


# --------------------------------------------------------------------------- #
# Multi-server session manager
# --------------------------------------------------------------------------- #
def _sys_exec() -> str:
    return os.environ.get("HANDAAS_MCP_PYTHON") or sys.executable or "python3"


class MultiMcpClient:
    """Manages one persistent MCP session per domain, reused across tool calls.

    Use as an async context manager so all sessions are closed cleanly::

        async with MultiMcpClient() as client:
            data = await client.call("risk", tool, args)
    """

    def __init__(self, domains: Optional[list[str]] = None) -> None:
        self._domains = domains or list(SERVER_REGISTRY)
        self._sessions: Dict[str, Any] = {}
        self._stack: contextlib.AsyncExitStack = contextlib.AsyncExitStack()

    async def __aenter__(self) -> "MultiMcpClient":
        await self._stack.__aenter__()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        # Close all sessions/streams; tolerate per-server shutdown errors so a
        # flaky stdio exit never masks real results.
        try:
            await self._stack.__aexit__(*exc)
        except BaseException as close_exc:  # noqa: BLE001 — best-effort cleanup
            if not isinstance(close_exc, ExceptionGroup):
                print(f"⚠️  MCP 连接关闭异常（已忽略）: {close_exc}", file=__import__("sys").stderr)
        self._sessions.clear()

    async def ensure_session(self, domain: str) -> Any:
        """Open (or reuse) a persistent session for *domain*."""
        if domain in self._sessions:
            return self._sessions[domain]
        conn = get_connection(domain)
        if not conn:
            raise MultiMcpError(
                f"未配置 MCP 连接 [{domain}]。请设置 SUPPLIER_EVALUATION_MCP_TOKEN 或 {REMOTE_URL_ENV.get(domain, 'HANDAAS_MCP_URL')}（Remote），"
                f"或设置 HANDAAS_MCP_SERVER_ROOT 指向 handaas-mcp-server 根目录（本地 stdio）。"
            )
        if conn["mode"] == "remote":
            session = await self._open_remote(conn["url"], conn.get("token", ""))
        else:
            session = await self._open_local(conn["server_path"])
        self._sessions[domain] = session
        return session

    async def _open_remote(self, url: str, token: str) -> Any:
        try:
            import httpx
            from mcp import ClientSession
            from mcp.client.streamable_http import streamable_http_client
        except Exception as exc:  # pragma: no cover
            raise MultiMcpError("需要 pip install 'mcp>=1.6.0' httpx") from exc
        headers: Dict[str, str] = {}
        if token and "token=" not in url:
            headers["Authorization"] = f"Bearer {token}"
        http_client = await self._stack.enter_async_context(
            httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(120, read=300), follow_redirects=True)
        )
        streams = await self._stack.enter_async_context(streamable_http_client(url=url, http_client=http_client))
        read_stream, write_stream, *_ = streams
        session = await self._stack.enter_async_context(ClientSession(read_stream, write_stream))
        await session.initialize()
        return session

    async def _open_local(self, server_path: str) -> Any:
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except Exception as exc:  # pragma: no cover
            raise MultiMcpError("需要 pip install 'mcp>=1.6.0'") from exc
        server_cwd = str(pathlib.Path(server_path).resolve().parents[1])
        wrapper = str(pathlib.Path(__file__).resolve().parents[2] / "assets" / "mcp_server_wrapper.py")
        params = StdioServerParameters(command=_sys_exec(), args=[wrapper, server_path], env=None, cwd=server_cwd)
        streams = await self._stack.enter_async_context(stdio_client(params))
        read_stream, write_stream, *_ = streams
        session = await self._stack.enter_async_context(ClientSession(read_stream, write_stream))
        await session.initialize()
        return session

    async def call(self, domain: str, tool: str, arguments: Dict[str, Any], *, timeout: int = 90) -> Any:
        """Call *tool* on *domain*'s MCP and return the extracted result.

        All errors (connection, timeout, protocol) are caught and returned as
        ``{"_error": ...}`` — never raised — so batch callers stay robust.
        """
        try:
            session = await self.ensure_session(domain)
            result = await asyncio.wait_for(session.call_tool(tool, arguments), timeout=timeout)
            return _extract_tool_result(result)
        except Exception as exc:
            return {"_error": f"[{domain}:{tool}] {exc}"}

    async def list_tools(self, domain: str) -> Any:
        session = await self.ensure_session(domain)
        return _plain(await session.list_tools())

    async def warmup(self, domains: list[str]) -> None:
        """Open sessions sequentially BEFORE concurrent calls.

        Spawning 5 stdio MCP servers at once can exhaust resources or trip the
        MCP SDK's internal TaskGroup; establishing them one-by-one is far more
        reliable, and the sessions are then reused by concurrent tool calls.
        """
        for d in domains:
            try:
                await self.ensure_session(d)
            except Exception as exc:
                print(f"⚠️  连接 [{d}] 失败: {exc}", file=__import__("sys").stderr)

    async def call_many(self, calls: list[tuple[str, str, str, Dict[str, Any]]]) -> Dict[str, Any]:
        """Concurrently call multiple tools. ``calls`` = [(key, domain, tool, args), ...].

        Sessions are warmed up sequentially first; tool calls then run
        concurrently with full per-call error isolation.
        """
        # 1. Establish all sessions sequentially (robust against stdio churn)
        needed = []
        for _k, domain, _t, _a in calls:
            if domain not in needed:
                needed.append(domain)
        await self.warmup(needed)
        # 2. Fan out tool calls concurrently (each call() catches its own errors)
        async def _one(key: str, domain: str, tool: str, args: Dict[str, Any]) -> tuple[str, Any]:
            return key, await self.call(domain, tool, args)
        results: Dict[str, Any] = {}
        tasks = [asyncio.ensure_future(_one(k, d, t, a)) for k, d, t, a in calls]
        for coro in asyncio.as_completed(tasks):
            try:
                key, value = await coro
                results[key] = value
            except Exception as exc:
                # last-resort isolation: should not reach here because call() swallows errors
                results[f"_task_error_{len(results)}"] = {"_error": str(exc)}
        return results
        return results
