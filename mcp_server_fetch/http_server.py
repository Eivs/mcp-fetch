"""HTTP server for MCP fetch with Bearer token authentication."""

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import AnyUrl, Field

from .server import fetch_url

# Initialize FastMCP server
# json_response=False enables SSE streaming
# stateless_http=False maintains persistent connections
mcp = FastMCP(name="mcp-fetch", json_response=False, stateless_http=False)


class FetchArgs:
    """Arguments for fetch tool."""

    url: Annotated[AnyUrl, Field(description="URL to fetch")]
    max_length: Annotated[
        int,
        Field(
            default=5000,
            description="Maximum number of characters to return.",
            gt=0,
            lt=1000000,
        ),
    ]
    start_index: Annotated[
        int,
        Field(
            default=0,
            description="On return output starting at this character index, useful if a previous fetch was truncated and more context is required.",
            ge=0,
        ),
    ]
    raw: Annotated[
        bool,
        Field(
            default=False,
            description="Get the actual HTML content of the requested page, without simplification.",
        ),
    ]


# Global configuration
USER_AGENT_AUTONOMOUS = None
USER_AGENT_MANUAL = None
PROXY_URL = None


def configure_server(
    custom_user_agent: str | None = None,
    proxy_url: str | None = None,
):
    """Configure the HTTP server settings.

    Args:
        custom_user_agent: Optional custom User-Agent string to use for requests
        proxy_url: Optional proxy URL to use for requests
    """
    global USER_AGENT_AUTONOMOUS, USER_AGENT_MANUAL, PROXY_URL

    DEFAULT_USER_AGENT_AUTONOMOUS = "ModelContextProtocol/1.0 (Autonomous; +https://github.com/modelcontextprotocol/servers)"
    DEFAULT_USER_AGENT_MANUAL = "ModelContextProtocol/1.0 (User-Specified; +https://github.com/modelcontextprotocol/servers)"

    USER_AGENT_AUTONOMOUS = custom_user_agent or DEFAULT_USER_AGENT_AUTONOMOUS
    USER_AGENT_MANUAL = custom_user_agent or DEFAULT_USER_AGENT_MANUAL
    PROXY_URL = proxy_url


@mcp.tool()
async def fetch(
    url: str, max_length: int = 5000, start_index: int = 0, raw: bool = False
) -> str:
    """Fetches a URL from the internet and optionally extracts its contents as markdown.

    Although originally you did not have internet access, and were advised to refuse and tell the user this, this tool now grants you internet access. Now you can fetch the most up-to-date information and let the user know that.

        Args:
            url: URL to fetch
            max_length: Maximum number of characters to return (default: 5000)
            start_index: Start content from this character index (default: 0)
            raw: Get raw content without markdown conversion (default: false)

        Returns:
            The fetched and processed content
    """
    if not url:
        return "<error>URL is required</error>"

    # Fetch the URL directly without robots.txt check
    try:
        content, prefix = await fetch_url(
            url, USER_AGENT_AUTONOMOUS, force_raw=raw, proxy_url=PROXY_URL
        )
    except Exception as e:
        return f"<error>Failed to fetch {url}: {str(e)}</error>"

    original_length = len(content)
    if start_index >= original_length:
        return "<error>No more content available.</error>"

    truncated_content = content[start_index : start_index + max_length]
    if not truncated_content:
        return "<error>No more content available.</error>"

    actual_content_length = len(truncated_content)
    remaining_content = original_length - (start_index + actual_content_length)

    # Only add the prompt to continue fetching if there is still remaining content
    if actual_content_length == max_length and remaining_content > 0:
        next_start = start_index + actual_content_length
        truncated_content += f"\n\n<error>Content truncated. Call the fetch tool with a start_index of {next_start} to get more content.</error>"

    return f"{prefix}Contents of {url}:\n{truncated_content}"


def create_auth_middleware(app, token: str):
    """Create authentication middleware for Bearer token validation.

    Args:
        app: The ASGI application to wrap
        token: The expected Bearer token

    Returns:
        ASGI application with authentication middleware
    """

    async def auth_middleware(scope, receive, send):
        if scope["type"] == "http":
            # Get headers
            headers = dict(scope.get("headers", []))
            auth_header = headers.get(b"authorization", b"").decode("utf-8")

            # Check Bearer token
            expected_auth = f"Bearer {token}"
            if auth_header != expected_auth:
                # Send 401 Unauthorized response
                await send(
                    {
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [
                            [b"content-type", b"application/json"],
                            [b"www-authenticate", b"Bearer"],
                        ],
                    }
                )
                await send(
                    {
                        "type": "http.response.body",
                        "body": b'{"error": "Unauthorized", "message": "Invalid or missing Bearer token"}',
                    }
                )
                return

        # Token is valid or not an HTTP request, proceed
        await app(scope, receive, send)

    return auth_middleware


def get_app(auth_token: str | None = None):
    """Get the ASGI application, optionally with authentication.

    Args:
        auth_token: Optional Bearer token for authentication. If provided,
                   requests must include "Authorization: Bearer <token>" header.

    Returns:
        ASGI application
    """
    app = mcp.streamable_http_app

    if auth_token:
        app = create_auth_middleware(app, auth_token)

    return app


def serve_http(
    host: str = "localhost",
    port: int = 8000,
    auth_token: str | None = None,
    custom_user_agent: str | None = None,
    proxy_url: str | None = None,
):
    """Run the HTTP server with optional Bearer token authentication.

    Args:
        host: Host to bind to (default: localhost)
        port: Port to listen on (default: 8000)
        auth_token: Optional Bearer token for authentication
        custom_user_agent: Optional custom User-Agent string
        proxy_url: Optional proxy URL to use for requests
    """
    import uvicorn

    # Configure server settings
    configure_server(custom_user_agent, proxy_url)

    # Get app with optional authentication
    app = get_app(auth_token)

    # Print startup information
    print(f"Starting MCP fetch server on {host}:{port}")
    if auth_token:
        print("Authentication: Bearer token required")
    else:
        print("Authentication: None (public access)")

    # Run server
    uvicorn.run(app, host=host, port=port, log_level="info")
