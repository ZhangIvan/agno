from typing import Any, Dict, List

# Maps each built-in tool type to its required beta header.
_BETA_HEADERS: Dict[str, str] = {
    "web_search": "ark-beta-web-search",
    "image_process": "ark-beta-image-process",
    "knowledge_search": "ark-beta-knowledge-search",
    "mcp": "ark-beta-mcp",
}


def inject_builtin_tools(
    params: Dict[str, Any],
    *,
    web_search: bool = False,
    image_process: bool = False,
    knowledge_search: Dict[str, Any] | None = None,
    mcp_servers: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Inject Volcengine built-in tool configs and beta headers into request params."""
    tools: List[Dict[str, Any]] = []
    headers: Dict[str, str] = {}

    if web_search:
        tools.append({"type": "web_search"})
        headers[_BETA_HEADERS["web_search"]] = "true"

    if image_process:
        tools.append({"type": "image_process"})
        headers[_BETA_HEADERS["image_process"]] = "true"

    if knowledge_search is not None:
        tools.append({"type": "knowledge_search", **knowledge_search})
        headers[_BETA_HEADERS["knowledge_search"]] = "true"

    if mcp_servers is not None:
        for server in mcp_servers:
            tools.append({"type": "mcp", **server})
        headers[_BETA_HEADERS["mcp"]] = "true"

    if tools:
        params["tools"] = tools + params.get("tools", [])

    if headers:
        merged = params.get("extra_headers") or {}
        merged.update(headers)
        params["extra_headers"] = merged

    return params
