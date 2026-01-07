from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse, urlunparse

from dotenv import load_dotenv

from mcp.shared.exceptions import McpError
from mcp.types import ErrorData, INVALID_PARAMS, INTERNAL_ERROR

from fastmcp import FastMCP


from mars.tools.web_tools.io import (
    WebSearchArgs,
    WebSearchResult,
    WebFetchArgs,
    WebFetchResult,
    RawDocument,
    SearchQuery,
    SearchHit,
)

load_dotenv()

DEFAULT_USER_AGENT_AUTONOMOUS = (
    "ModelContextProtocol/1.0 (Autonomous; +https://github.com/modelcontextprotocol/servers)"
)
DEFAULT_USER_AGENT_MANUAL = (
    "ModelContextProtocol/1.0 (User-Specified; +https://github.com/modelcontextprotocol/servers)"
)

BROWSER_ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"

BROWSER_UA_FALLBACK = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
    "Edg/134.0.0.0"
)


def build_serper_wrapper(k: int):
    from langchain_community.utilities import GoogleSerperAPIWrapper

    return GoogleSerperAPIWrapper(k=k)


def web_search(args: WebSearchArgs) -> WebSearchResult:
    """Using GoogleSearch and Searching for the query."""
    sq = SearchQuery(q=args.query, k=args.k, recency_days=args.recency_days, domains=args.domains)

    wrapper = build_serper_wrapper(k=args.k)
    raw = wrapper.results(sq.q)
    organic = raw.get("organic", []) if isinstance(raw, dict) else []

    results: list[SearchHit] = []
    seen: set[str] = set()

    for idx, item in enumerate(organic, start=1):
        item = item or {}
        url = item.get("link") or ""
        if not url or url in seen:
            continue
        seen.add(url)

        if sq.domains:
            netloc = urlparse(url).netloc.lower()
            if not any(netloc.endswith(d.lower()) for d in sq.domains):
                continue

        results.append(
            SearchHit(
                url=url,
                title=item.get("title"),
                snippet=item.get("snippet"),
                rank=item.get("position") or idx,
            )
        )
        if len(results) >= sq.k:
            break

    return WebSearchResult(retrieved_at=datetime.now(timezone.utc), query=sq, results=results)


def simplify_html_to_markdown(html: str) -> str:
    from readabilipy import simple_json
    import markdownify

    ret = simple_json.simple_json_from_html_string(html, use_readability=True)
    if not ret.get("content"):
        return "<error>Page failed to be simplified from HTML</error>"
    return markdownify.markdownify(ret.get("content"), heading_style=markdownify.ATX)


def get_robots_txt_url(url: str) -> str:
    """Get the robots.txt URL for a given website URL"""
    parsed = urlparse(url)
    robots_url = urlunparse((parsed.scheme, parsed.netloc, "/robots.txt", "", "", ""))
    return robots_url


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


async def check_may_autonomously_fetch_url(url: str, user_agent: str, proxy_url: str | None = None) -> None:
    """
    Check if the URL can be fetched by the user agent according to the robots.txt file.
    Raises a McpError if not.
    """
    from httpx import AsyncClient, HTTPError
    from protego import Protego

    robots_url = get_robots_txt_url(url)

    async with AsyncClient(proxy=proxy_url) as client:
        try:
            resp = await client.get(
                robots_url,
                follow_redirects=True,
                headers={"User-Agent": user_agent},
                timeout=20.0,
            )
        except HTTPError:
            raise McpError(
                ErrorData(
                    code=INTERNAL_ERROR,
                    message=f"Failed to fetch robots.txt {robots_url} due to a connection issue.",
                )
            )

    if resp.status_code in (401, 403):
        raise McpError(
            ErrorData(
                code=INVALID_PARAMS,
                message=(
                    f"robots.txt returned {resp.status_code} for {robots_url}; "
                    "autonomous fetching is not allowed."
                ),
            )
        )

    if 400 <= resp.status_code < 500:
        return

    robots_txt = resp.text or ""
    processed = "\n".join(line for line in robots_txt.splitlines() if not line.strip().startswith("#"))
    parser = Protego.parse(processed)

    if not parser.can_fetch(str(url), user_agent):
        raise McpError(
            ErrorData(
                code=INTERNAL_ERROR,
                message=(
                    f"The sites robots.txt ({robots_url}), specifies that autonomous fetching of this page is not allowed, "
                    f"<useragent>{user_agent}</useragent>\n"
                    f"<url>{url}</url>"
                    f"<robots>\n{robots_txt}\n</robots>\n"
                    f"The assistant must let the user know that it failed to view the page. The assistant may provide further guidance based on the above information.\n"
                    f"The assistant can tell the user that they can try manually fetching the page by using the fetch prompt within their UI."
                ),
            )
        )


async def fetch_url(
    url: str,
    *,
    user_agent: str,
    timeout_s: float,
    force_raw: bool,
    proxy_url: Optional[str],
) -> RawDocument:
    from httpx import AsyncClient, HTTPError

    async with AsyncClient(proxy=proxy_url) as client:
        try:
            resp = await client.get(
                url,
                follow_redirects=True,
                headers={
                    "User-Agent": user_agent,
                    "Accept": BROWSER_ACCEPT,
                    "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
                },
                timeout=timeout_s,
            )
        except HTTPError as e:
            raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Failed to fetch {url}: {e!r}"))

        content_type = resp.headers.get("content-type") or ""
        status_code = resp.status_code

        if status_code >= 400:
            raise McpError(
                ErrorData(
                    code=INTERNAL_ERROR,
                    message=f"Failed to fetch {url} - status code {resp.status_code}",
                )
            )

    if "application/pdf" in content_type.lower():
        sha = sha256_bytes(resp.content)
        return RawDocument(
            content_type=content_type,
            text="PDF content is not supported. You should avoid crawl pdf content.",
            raw=None,
            sha256=sha,
        )

    page_text = resp.text or ""
    is_page_html = ("<html" in page_text[:100] or "text/html" in content_type or not content_type)

    if is_page_html and not force_raw:
        text = simplify_html_to_markdown(page_text)
    else:
        text = page_text

    sha = sha256_text(text)
    return RawDocument(content_type=content_type, text=text, raw=None, sha256=sha)


def slice_with_pagination(text: str, *, start_index: int, max_length: int) -> tuple[str, bool, Optional[int], Optional[str]]:
    """Return (chunk, truncated, next_start_index, note)."""
    original_length = len(text)

    if start_index >= original_length:
        return "<error>No more content available.</error>", False, None, "start_index beyond content length"

    chunk = text[start_index : start_index + max_length]
    if not chunk:
        return "<error>No more content available.</error>", False, None, "empty slice"

    truncated = (start_index + len(chunk)) < original_length
    next_start = (start_index + len(chunk)) if truncated else None
    note = None
    if truncated:
        note = f"Content truncated. Call web_fetch with start_index={next_start} to retrieve the next chunk."

    return chunk, truncated, next_start, note


async def web_fetch(
    args: WebFetchArgs,
    *,
    ignore_robots_txt: bool,
    user_agent: str,
    proxy_url: Optional[str] = None,
) -> WebFetchResult:
    url = str(args.url)

    if not ignore_robots_txt:
        await check_may_autonomously_fetch_url(url, user_agent, proxy_url)

    doc = await fetch_url(
        url,
        user_agent=user_agent,
        timeout_s=args.timeout_s,
        force_raw=args.raw,
        proxy_url=proxy_url,
    )

    if doc.text:
        chunk, truncated, next_start, note = slice_with_pagination(
            doc.text, start_index=args.start_index, max_length=args.max_length
        )
        doc = doc.model_copy(update={"text": chunk})
    else:
        truncated = False
        next_start = None
        note = "Binary content or empty text (e.g., PDF)."

    return WebFetchResult(
        retrieved_at=datetime.now(timezone.utc),
        url=url,
        document=doc,
        truncated=truncated,
        next_start_index=next_start,
        note=note,
    )


def json_text(payload: Any) -> str:
    """Serialize payload to JSON text with stable UTF-8 output."""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def create_fastmcp_app(
    *,
    custom_user_agent: str | None = None,
    ignore_robots_txt: bool = False,
    proxy_url: str | None = None,
) -> FastMCP:
    """
    Build the FastMCP server object, keeping original tool names, prompt names,
    and returning JSON text payloads exactly like your stdio implementation.
    """
    user_agent_autonomous = custom_user_agent if custom_user_agent else DEFAULT_USER_AGENT_AUTONOMOUS

    mcp = FastMCP(name="web-mcp-server")

    # -------- Tools --------
    @mcp.tool(
        name="web_search",
        description=(
            "Search the web and return structured results (title/url/snippet). "
            "Use this before web_fetch to obtain candidate URLs."
        ),
    )
    def tool_web_search(
        query: str,
        k: int = 10,
        recency_days: int | None = None,
        domains: list[str] | None = None,
    ) -> str:
        """
        Returns JSON text of WebSearchResult (same as your previous TextContent JSON).
        """
        try:
            args = WebSearchArgs(query=query, k=k, recency_days=recency_days, domains=domains)
            result = web_search(args)
            return json_text(result.model_dump(mode="json"))
        except McpError:
            raise
        except Exception as e:
            raise McpError(ErrorData(code=INTERNAL_ERROR, message=str(e)))

    @mcp.tool(
        name="web_fetch",
        description=(
            "Fetch a URL and return extracted text (markdown if HTML) plus metadata. "
            "Supports pagination via start_index/max_length."
        ),
    )
    async def tool_web_fetch(
        url: str,
        timeout_s: float = 20.0,
        raw: bool = False,
        start_index: int = 0,
        max_length: int = 20000,
    ) -> str:
        """
        Returns JSON text of WebFetchResult (same as your previous TextContent JSON).
        """
        try:
            args = WebFetchArgs(
                url=url,
                timeout_s=timeout_s,
                raw=raw,
                start_index=start_index,
                max_length=max_length,
            )
            result = await web_fetch(
                args,
                ignore_robots_txt=ignore_robots_txt,
                user_agent=user_agent_autonomous,
                proxy_url=proxy_url,
            )
            return json_text(result.model_dump(mode="json"))
        except McpError:
            raise
        except Exception as e:
            raise McpError(ErrorData(code=INTERNAL_ERROR, message=str(e)))

    @mcp.prompt(
        name="web_search",
        description="Web search for relevant sources. You should use this tool first to collect candidate URLs.",
    )
    def prompt_web_search(query: str) -> str:
        return f"Web search for relevant sources about: {query}"

    @mcp.prompt(
        name="web_fetch",
        description=(
            "Fetch page content for a specific URL. "
            "You should avoid crawl from pdf page like: "
            "https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf"
        ),
    )
    def prompt_web_fetch(url: str) -> str:
        return f"Fetch page content for URL: {url}"

    return mcp


def main():
    host = "0.0.0.0"
    port = 8000

    mcp = create_fastmcp_app(
        custom_user_agent=None,
        ignore_robots_txt=False,
        proxy_url=None,
    )

    mcp.run(transport="http", host=host, port=port)


if __name__ == "__main__":
    main()
