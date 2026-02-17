"""Run FreeFeed MCP Server as a module."""

import asyncio
import os
from pathlib import Path

from .server import main


async def run_api_server():
    """Run REST API server with optional dual HTTP+HTTPS support."""
    import uvicorn

    from .api import app

    host = os.getenv("FREEFEED_API_HOST", "0.0.0.0")
    http_port = int(os.getenv("FREEFEED_API_PORT", "8000"))
    https_port = int(os.getenv("FREEFEED_API_HTTPS_PORT", "8443"))

    # Check if SSL is enabled
    ssl_enabled = os.getenv("FREEFEED_SSL_ENABLED", "").lower() in {"1", "true", "yes"}

    # Build cert paths if SSL enabled
    ssl_config = {}
    if ssl_enabled:
        cert_dir = Path(__file__).parent.parent / "certs"
        cert_file = cert_dir / "cert.pem"
        key_file = cert_dir / "key.pem"

        if cert_file.exists() and key_file.exists():
            ssl_config = {
                "ssl_keyfile": str(key_file),
                "ssl_certfile": str(cert_file),
            }
            print(f"🔐 SSL certificates found: {cert_file}")
        else:
            print(f"⚠️  SSL_ENABLED but certificates not found at {cert_dir}")
            print(f"   Expected: {cert_file} and {key_file}")
            ssl_enabled = False

    if ssl_enabled and ssl_config:
        # Run both HTTP and HTTPS servers
        print("🚀 Starting FreeFeed API servers:")
        print(f"   🌐 HTTP  on  {host}:{http_port}")
        print(f"   🔐 HTTPS on {host}:{https_port}")
        print(f"   📚 Docs on http://{host}:{http_port}/docs")

        # Create configs for both servers
        config_http = uvicorn.Config(app, host=host, port=http_port, log_level="info")
        config_https = uvicorn.Config(
            app, host=host, port=https_port, log_level="info", **ssl_config
        )

        server_http = uvicorn.Server(config_http)
        server_https = uvicorn.Server(config_https)

        # Run both servers concurrently
        await asyncio.gather(server_http.serve(), server_https.serve())
    else:
        # Run only HTTP server
        port = http_port
        print(f"🚀 Starting FreeFeed API server on {host}:{port}")
        print(f"📚 Docs available at http://{host}:{port}/docs")

        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()


if __name__ == "__main__":
    # Detect if running in Docker/API mode
    # Set FREEFEED_API_MODE=1 to run REST API server instead of MCP stdio server
    api_mode = os.getenv("FREEFEED_API_MODE", "").lower() in {"1", "true", "yes"}

    if api_mode:
        # Run REST API server (for Docker/production)
        asyncio.run(run_api_server())
    else:
        # Run MCP stdio server (for Claude Desktop)
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            pass
