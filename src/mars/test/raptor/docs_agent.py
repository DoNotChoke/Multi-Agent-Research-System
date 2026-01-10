import asyncio

from langchain.agents import create_agent
from langchain_core.messages import ToolMessage

from mars.tools.lead_tools.run_agent import run_researcher
from mars.tools.mcp_tools import get_docs_tools


async def docs_agent():
    tools = await get_docs_tools(stateful=False, http=True)
    agent = create_agent("gpt-5-mini", tools)
    resp = await run_researcher(
        worker_graph=agent,
        prompt="What datasets are used for experiment in BitDistill paper?"
    )
    subagent_message = []
    for message in resp["messages"]:
        if isinstance(message, ToolMessage):
            continue
        subagent_message.append(message)

    print(subagent_message)

if __name__ == '__main__':
    asyncio.run(docs_agent())