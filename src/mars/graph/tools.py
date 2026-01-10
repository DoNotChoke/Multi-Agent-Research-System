import asyncio

from mars.tools.mcp_tools import get_web_tools, get_tools, get_docs_tools


async def get_available_tools():
    tools = []
    web_tools = await get_web_tools(stateful=False, http=True)
    docs_tools = await get_docs_tools(stateful=False, http=True)
    tools.extend(web_tools)
    tools.extend(docs_tools)
    return tools

if __name__ == '__main__':
    print(asyncio.run(get_available_tools()))
