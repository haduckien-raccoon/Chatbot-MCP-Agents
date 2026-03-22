from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from config.settings import settings


def _resolve_env_placeholders(value: str) -> str:
    raw = str(value or "")
    if raw.startswith("${") and raw.endswith("}"):
        return os.getenv(raw[2:-1], "")
    if raw.startswith("$") and len(raw) > 1:
        return os.getenv(raw[1:], "")
    return raw


def _stringify_content_item(item: Any) -> str:
    text = getattr(item, "text", None)
    if text:
        return str(text).strip()

    data = getattr(item, "data", None)
    if data is not None:
        try:
            return json.dumps(data, ensure_ascii=False, indent=2)
        except TypeError:
            return str(data).strip()

    if isinstance(item, dict):
        if item.get("text"):
            return str(item["text"]).strip()
        if "data" in item:
            try:
                return json.dumps(item["data"], ensure_ascii=False, indent=2)
            except TypeError:
                return str(item["data"]).strip()

    return str(item).strip()


def _result_to_text(result: Any) -> str:
    parts: list[str] = []
    for item in getattr(result, "content", []) or []:
        text = _stringify_content_item(item)
        if text:
            parts.append(text)
    return "\n\n".join(parts).strip()


def _extract_context7_library_id(text: str) -> str:
    match = re.search(r"(/\S+/\S+(?:/\S+)?)", text or "")
    return match.group(1).rstrip(".,)") if match else ""


def _guess_library_name(query: str) -> str:
    text = (query or "").strip()
    if not text:
        return ""

    quoted = re.findall(r'["“](.+?)["”]', text)
    if quoted:
        return quoted[0].strip()

    for marker in (" về ", " ve ", " cho ", " with ", " dùng ", " dung ", " using "):
        if marker in f" {text.lower()} ":
            idx = text.lower().find(marker.strip())
            if idx >= 0:
                candidate = text[idx + len(marker.strip()):].strip(" :,-")
                if candidate:
                    return candidate

    return text


@dataclass
class ExternalMcpServer:
    name: str
    session: ClientSession
    stack: contextlib.AsyncExitStack
    tools: list[Any]
    config: dict[str, Any]


class ExternalMcpManager:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._servers: dict[str, ExternalMcpServer] = {}
        self._initialized = False

    async def _initialize(self) -> None:
        if self._initialized:
            return

        config_path = Path(settings.external_mcp_config_path)
        if not config_path.is_absolute():
            config_path = Path.cwd() / config_path

        if not config_path.exists():
            self._initialized = True
            return

        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            self._initialized = True
            return

        for name, server_config in (payload.get("mcpServers") or {}).items():
            server = await self._connect_server(name, server_config)
            if server:
                self._servers[name] = server

        self._initialized = True

    async def _connect_server(self, name: str, server_config: dict[str, Any]) -> ExternalMcpServer | None:
        command = str(server_config.get("command") or "").strip()
        if not command:
            return None

        args = [str(arg) for arg in server_config.get("args") or []]
        cwd = str(server_config.get("cwd") or Path.cwd())
        env = dict(os.environ)
        for key, value in (server_config.get("env") or {}).items():
            resolved = _resolve_env_placeholders(str(value))
            if resolved:
                env[str(key)] = resolved

        stack = contextlib.AsyncExitStack()
        try:
            params = StdioServerParameters(command=command, args=args, cwd=cwd, env=env)
            read, write = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read, write))
            await asyncio.wait_for(session.initialize(), timeout=settings.external_mcp_timeout_ms / 1000)
            tools_result = await asyncio.wait_for(session.list_tools(), timeout=settings.external_mcp_timeout_ms / 1000)
            return ExternalMcpServer(
                name=name,
                session=session,
                stack=stack,
                tools=list(getattr(tools_result, "tools", []) or []),
                config=server_config,
            )
        except Exception:
            await stack.aclose()
            return None

    async def ensure_initialized(self) -> None:
        async with self._lock:
            await self._initialize()

    async def search_it_context(self, query: str) -> str:
        if not settings.external_mcp_enabled:
            return ""

        await self.ensure_initialized()
        if not self._servers:
            return ""

        sections: list[str] = []
        for server in self._servers.values():
            try:
                section = await self._query_server(server, query)
            except Exception:
                section = ""
            if section:
                sections.append(section)

        return "\n\n".join(sections).strip()

    async def _query_server(self, server: ExternalMcpServer, query: str) -> str:
        integration = server.config.get("integration") or {}
        mode = str(integration.get("mode") or "").strip().lower()

        if mode == "tool":
            tool_name = str(integration.get("tool") or "").strip()
            if not tool_name:
                return ""
            args = self._render_args(integration.get("args") or {}, query=query)
            text = await self._call_tool(server, tool_name, args)
            return f"[MCP {server.name}]\n{text}" if text else ""

        if mode == "context7" or server.name.lower() == "context7":
            text = await self._query_context7(server, query, integration)
            return f"[MCP {server.name}]\n{text}" if text else ""

        tool_name = self._pick_default_tool(server)
        if not tool_name:
            return ""
        text = await self._call_tool(server, tool_name, {"query": query})
        return f"[MCP {server.name}]\n{text}" if text else ""

    def _pick_default_tool(self, server: ExternalMcpServer) -> str:
        names = {getattr(tool, "name", "") for tool in server.tools}
        lowered = server.name.lower()

        if lowered == "brave" and "brave_web_search" in names:
            return "brave_web_search"
        if lowered == "github" and "search_repositories" in names:
            return "search_repositories"
        return ""

    def _render_args(self, template: dict[str, Any], **values: str) -> dict[str, Any]:
        rendered: dict[str, Any] = {}
        for key, value in template.items():
            if isinstance(value, str):
                current = value
                for name, replacement in values.items():
                    current = current.replace(f"{{{name}}}", replacement)
                rendered[key] = current
            else:
                rendered[key] = value
        return rendered

    async def _query_context7(
        self,
        server: ExternalMcpServer,
        query: str,
        integration: dict[str, Any],
    ) -> str:
        tool_names = {getattr(tool, "name", "") for tool in server.tools}
        resolve_tool = str(integration.get("resolve_tool") or "resolve-library-id")
        docs_tool = str(integration.get("docs_tool") or "")

        if not docs_tool:
            if "query-docs" in tool_names:
                docs_tool = "query-docs"
            elif "get-library-docs" in tool_names:
                docs_tool = "get-library-docs"

        if resolve_tool not in tool_names or docs_tool not in tool_names:
            return ""

        library_name = _guess_library_name(query)
        resolve_args = {"libraryName": library_name}
        if resolve_tool == "resolve-library-id":
            resolve_schema = next((tool for tool in server.tools if getattr(tool, "name", "") == resolve_tool), None)
            resolve_required = set((((getattr(resolve_schema, "inputSchema", None) or {}).get("required")) or []))
            if "query" in resolve_required:
                resolve_args["query"] = query

        resolve_text = await self._call_tool(server, resolve_tool, resolve_args)
        library_id = _extract_context7_library_id(resolve_text)
        if not library_id:
            return resolve_text

        if docs_tool == "query-docs":
            docs_args = {"query": query, "libraryId": library_id}
        else:
            docs_args = {
                "context7CompatibleLibraryID": library_id,
                "topic": query,
            }

        docs_text = await self._call_tool(server, docs_tool, docs_args)
        if not docs_text:
            return resolve_text

        return "\n".join(
            [
                f"Library: {library_id}",
                docs_text,
            ]
        ).strip()

    async def _call_tool(self, server: ExternalMcpServer, tool_name: str, args: dict[str, Any]) -> str:
        result = await asyncio.wait_for(
            server.session.call_tool(tool_name, args),
            timeout=settings.external_mcp_timeout_ms / 1000,
        )
        return _result_to_text(result)


_manager = ExternalMcpManager()


async def search_external_it_context(query: str) -> str:
    return await _manager.search_it_context(query)
