from .server import serve


def main():
    """MCP Fetch Server - HTTP fetching functionality for MCP"""
    import argparse
    import asyncio
    import os
    from pathlib import Path

    # Load environment variables from files
    try:
        from dotenv import load_dotenv

        # Try to load .env files from current directory, /etc/default/, or parent directory
        env_paths = [
            Path.cwd() / ".env",
            Path("/etc/default/mcp-fetch"),
            Path(__file__).parent.parent / ".env",
        ]
        for env_path in env_paths:
            if env_path.exists():
                load_dotenv(env_path)
                break
    except ImportError:
        pass  # python-dotenv not installed, skip

    parser = argparse.ArgumentParser(
        description="give a model the ability to make web requests"
    )

    # Transport mode
    parser.add_argument(
        "--transport",
        type=str,
        choices=["stdio", "http"],
        default=os.getenv("TRANSPORT", "stdio"),
        help="Transport mode: stdio (default) or http",
    )

    # HTTP-specific options
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("HOST", "localhost"),
        help="Host to bind HTTP server to (default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "8000")),
        help="Port for HTTP server (default: 8000)",
    )
    parser.add_argument(
        "--auth-token",
        type=str,
        default=os.getenv("AUTH_TOKEN"),
        help="Bearer token for HTTP authentication (optional)",
    )

    # Common options
    parser.add_argument(
        "--user-agent",
        type=str,
        default=os.getenv("CUSTOM_USER_AGENT"),
        help="Custom User-Agent string",
    )
    parser.add_argument(
        "--proxy-url",
        type=str,
        default=os.getenv("PROXY_URL"),
        help="Proxy URL to use for requests",
    )

    args = parser.parse_args()

    if args.transport == "http":
        # Use HTTP transport with Streamable HTTP protocol
        from .http_server import serve_http

        serve_http(
            host=args.host,
            port=args.port,
            auth_token=args.auth_token,
            custom_user_agent=args.user_agent,
            proxy_url=args.proxy_url,
        )
    else:
        # Use stdio transport (default)
        asyncio.run(serve(args.user_agent, args.proxy_url))


if __name__ == "__main__":
    main()
