
import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def list_server_tools():
    project_root = Path(__file__).resolve().parents[1]
    server_file = project_root / "src" / "deployops" / "server.py"

    params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_file)],
        cwd=str(project_root),
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return {tool.name for tool in result.tools}


def test_mcp_server_exposes_expected_tools():
    tools = asyncio.run(list_server_tools())

    assert {
        "get_deploy_status",
        "list_failed_builds",
        "create_jira_incident",
        "rollback_service",
    }.issubset(tools)
