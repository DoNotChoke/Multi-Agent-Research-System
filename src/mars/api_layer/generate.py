from langchain.tools import Tool
from langchain_core.runnables import Runnable

from typing import AsyncGenerator

async def generate_stream(
        graph,
        tool: Tool,
        question: str
) -> AsyncGenerator[str, None]:
        """Generate"""