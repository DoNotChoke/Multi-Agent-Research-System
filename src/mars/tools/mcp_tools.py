from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Mapping, Optional, Literal

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools


def _find_repo_root(start: Optional[Path] = None) -> Optional[Path]:
    p = (start or Path.cwd()).resolve()
    for parent in [p, *p.parents]:
        if (parent / "mars").exists():
            return parent
    return None


def stdio_connection(
        *,
        command: str,
        args: list[str],
        env: Optional[Mapping[str, str]] = None,
        cwd: Optional[str | Path] = None
) -> dict[str, Any]:
    """
    Build a stdio connection config
    """
    conn: dict[str, Any] = {
        "transport": "stdio",
        "command": command,
        "args": args,
    }
    if env:
        conn["env"] = dict(env)
    if cwd is not None:
        conn["cwd"] = str(cwd)
    return conn


def http_connection(
        *,
        url: str,
        headers: Optional[Mapping[str, str]] = None,
        auth: Any = None
) -> dict[str, Any]:
    """
    Build an HTTP (streamable-http) connection config.
    """
    conn: dict[str, Any] = {"transport": "http", "url": url}
    if headers:
        conn["headers"] = dict(headers)
    if auth is not None:
        conn["auth"] = auth
    return conn


def build_mcp_connections(
        *,
        server_name: str = "web_mcp_server",
        transport: Literal["stdio", "http"] = "stdio",
        # ---- stdio only ----
        python_executable: Optional[str] = None,
        tools_path: Optional[str | Path] = None,
        tools_module: Optional[str] = "mars.tools.web_tools.tools",
        env: Optional[Mapping[str, str]] = None,
        cwd: Optional[str | Path] = None,
        # ---- http only ----
        url: Optional[str] = None,
        headers: Optional[Mapping[str, str]] = None,
        auth: Any = None,
) -> dict[str, Any]:

    if transport == "http":
        if not url:
            raise ValueError("url must be provided when transport='http'. Example: http://localhost:8000/mcp")
        return {
            server_name: http_connection(url=url, headers=headers, auth=auth)
        }

    python = python_executable or "python"

    if cwd is None:
        repo_root = _find_repo_root()
        cwd = repo_root if repo_root else None

    if tools_path and tools_module:
        raise ValueError("Provide only one of web_tools_path or web_tools_module.")

    if tools_path:
        args = [str(Path(tools_path).resolve())]
    else:
        if not tools_module:
            raise ValueError("web_tools_module must be provided when web_tools_path is not set.")
        args = ["-m", tools_module]

    return {
        server_name: stdio_connection(
            command=python,
            args=args,
            env=env,
            cwd=cwd
        )
    }


async def get_tools(
        connections: Mapping[str, Any],
        *,
        tool_name_prefix: bool = False,
        stateful: bool = False,
):
    server_name = list(connections.keys())[0]
    client = MultiServerMCPClient(dict(connections), tool_name_prefix=tool_name_prefix)
    if stateful:
        async with client.session(server_name) as session:
            tools = await load_mcp_tools(session)
            return tools

    tools = await client.get_tools()
    return tools

async def get_web_tools(stateful: bool = False, http: bool = False):
    transport = "http" if http else "stdio"
    conn = build_mcp_connections(
        server_name="web_mcp_server",
        transport=transport,
        tools_module="mars.tools.web_tools.tools",
        url="http://localhost:8000/mcp",
    )
    return await get_tools(connections=conn, stateful=stateful)

async def get_docs_tools(stateful: bool = False, http: bool = False):
    transport = "http" if http else "stdio"
    conn = build_mcp_connections(
        server_name="docs_mcp_server",
        transport=transport,
        tools_module="mars.tools.docs_tools.tools",
        url="http://localhost:8010/mcp",
    )
    return await get_tools(connections=conn, stateful=stateful)


