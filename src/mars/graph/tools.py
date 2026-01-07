from mars.tools.mcp_tools import get_tools, get_web_tools


async def get_available_tools():
    tools = []
    web_tools = await get_web_tools(stateful=False, http=False)
    tools.extend(web_tools)
    return tools
