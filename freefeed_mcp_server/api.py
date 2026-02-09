"""FreeFeed REST API - HTTP wrapper for MCP server."""

import asyncio
import contextlib
import io
import logging
import os
import uuid
from dataclasses import dataclass
from typing import Annotated, Any, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .ai_agent import AssistantRequest, AssistantResponse, run_assistant
from .client import FreeFeedAPIError, FreeFeedAuthError, FreeFeedClient

# Load environment variables
load_dotenv()


def _resolve_log_level() -> int:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    return getattr(logging, level_name, logging.INFO)


# Setup logging
logging.basicConfig(
    level=_resolve_log_level(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _compact_user(user_data: dict) -> dict:
    fields = ["id", "username", "screenName", "type", "isPrivate", "isProtected"]
    return {key: user_data.get(key) for key in fields if key in user_data}


def _compact_whoami(payload: dict) -> dict:
    users = payload.get("users")
    subscriptions = payload.get("subscriptions")
    subscribers = payload.get("subscribers")

    compacted: dict = {}
    if isinstance(users, dict):
        compacted["users"] = _compact_user(users)

    def _compact_list(items: Any) -> list[dict]:
        if not isinstance(items, list):
            return []
        return [_compact_user(item) for item in items if isinstance(item, dict)]

    if subscriptions is not None:
        compacted["subscriptions"] = _compact_list(subscriptions)
    if subscribers is not None:
        compacted["subscribers"] = _compact_list(subscribers)

    compacted["summary"] = {
        "subscriptions": len(compacted.get("subscriptions", [])),
        "subscribers": len(compacted.get("subscribers", [])),
    }
    return compacted


def _is_valid_user(user: Any) -> bool:
    """Check if user has required id and username fields."""
    return (
        isinstance(user, dict) and bool(user.get("id")) and bool(user.get("username"))
    )


def _build_user_map(users: Any) -> dict[str, str]:
    """Build a mapping of user IDs to usernames."""
    if not isinstance(users, list):
        return {}
    return {user["id"]: user["username"] for user in users if _is_valid_user(user)}


def _set_post_url(post: dict, base_url: str, user_map: dict[str, str]) -> None:
    """Set the postUrl for a single post."""
    if not isinstance(post, dict):
        return
    post_id = post.get("id")
    short_id = post.get("shortId")
    author_id = post.get("createdBy")
    username = user_map.get(author_id)

    if username and short_id:
        post["postUrl"] = f"{base_url}/{username}/{short_id}"
    elif post_id:
        post["postUrl"] = f"{base_url}/posts/{post_id}"


def _add_post_urls(payload: Any, base_url: str) -> Any:
    if not isinstance(payload, dict):
        return payload

    user_map = _build_user_map(payload.get("users"))
    posts = payload.get("posts")

    if isinstance(posts, list):
        for post in posts:
            _set_post_url(post, base_url, user_map)
    elif isinstance(posts, dict):
        _set_post_url(posts, base_url, user_map)

    return payload


# Initialize FastAPI app
app = FastAPI(
    title="FreeFeed API",
    description="REST API for FreeFeed MCP server",
    version="0.1.0",
)

# Global client instance
freefeed_client: Optional[FreeFeedClient] = None

# In-memory API sessions
SESSION_STORE: dict[str, "SessionData"] = {}
SESSION_LOCK = asyncio.Lock()


async def get_client() -> FreeFeedClient:
    """Get or create FreeFeed client instance."""
    global freefeed_client

    if freefeed_client is None:
        base_url = os.getenv("FREEFEED_BASE_URL", "https://freefeed.net")
        api_version_raw = os.getenv("FREEFEED_API_VERSION")
        app_token = os.getenv("FREEFEED_APP_TOKEN")
        username = os.getenv("FREEFEED_USERNAME")
        password = os.getenv("FREEFEED_PASSWORD")

        api_version: Optional[int] = None
        if api_version_raw:
            try:
                api_version = int(api_version_raw)
            except ValueError:
                logger.warning(
                    "Invalid FREEFEED_API_VERSION=%s; using default", api_version_raw
                )

        if not app_token and (not username or not password):
            raise HTTPException(
                status_code=500,
                detail="Set FREEFEED_APP_TOKEN or FREEFEED_USERNAME and FREEFEED_PASSWORD",
            )

        freefeed_client = FreeFeedClient(
            base_url=base_url,
            username=username,
            password=password,
            auth_token=app_token,
            api_version=api_version,
        )

        if app_token:
            logger.info("FreeFeed client initialized with application token")
        else:
            try:
                await freefeed_client.authenticate()
                logger.info("FreeFeed client initialized and authenticated")
            except FreeFeedAuthError as e:
                raise HTTPException(status_code=401, detail=str(e))

    return freefeed_client


@dataclass
class SessionData:
    auth_token: str
    base_url: str
    api_version: Optional[int]
    username: Optional[str] = None


class SessionCreate(BaseModel):
    auth_token: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    base_url: Optional[str] = None
    api_version: Optional[int] = None


class SessionResponse(BaseModel):
    session_token: str
    user: Optional[dict[str, Any]] = None


async def _create_client_from_credentials(
    *,
    auth_token: Optional[str],
    username: Optional[str],
    password: Optional[str],
    base_url: Optional[str],
    api_version: Optional[int],
) -> FreeFeedClient:
    if auth_token and (username or password):
        raise HTTPException(
            status_code=400,
            detail="Use either auth_token or username/password, not both",
        )
    if not auth_token and (not username or not password):
        raise HTTPException(
            status_code=400,
            detail="Provide auth_token or username and password",
        )

    client = FreeFeedClient(
        base_url=base_url or os.getenv("FREEFEED_BASE_URL", "https://freefeed.net"),
        username=username,
        password=password,
        auth_token=auth_token,
        api_version=api_version,
    )

    if auth_token:
        await client.whoami()
    else:
        await client.authenticate()

    return client


async def _get_client_for_request(request: Request) -> FreeFeedClient:
    if request is None:
        return await get_client()

    auth_token = request.headers.get("X-Freefeed-Auth-Token")
    auth_header = request.headers.get("Authorization")
    if not auth_token and auth_header:
        if auth_header.lower().startswith("bearer "):
            auth_token = auth_header.split(" ", 1)[1].strip()

    username = request.headers.get("X-Freefeed-Username")
    password = request.headers.get("X-Freefeed-Password")
    session_token = request.headers.get("X-Session-Token")

    if auth_token or (username and password):
        client = await _create_client_from_credentials(
            auth_token=auth_token,
            username=username,
            password=password,
            base_url=request.headers.get("X-Freefeed-Base-Url"),
            api_version=None,
        )
        request.state.request_client = client
        return client

    if session_token:
        async with SESSION_LOCK:
            session = SESSION_STORE.get(session_token)
        if not session:
            raise HTTPException(status_code=401, detail="Invalid session token")

        client = FreeFeedClient(
            base_url=session.base_url,
            auth_token=session.auth_token,
            api_version=session.api_version,
        )
        request.state.request_client = client
        return client

    return await get_client()


@app.middleware("http")
async def _close_request_client(request: Request, call_next):
    request.state.request_client = None
    response = await call_next(request)
    client = getattr(request.state, "request_client", None)
    if client is not None and client is not freefeed_client:
        await client.close()
    return response


# Pydantic models for request/response


class PostCreate(BaseModel):
    body: str
    group_names: Optional[List[str]] = None


class PostUpdate(BaseModel):
    body: str


class CommentCreate(BaseModel):
    body: str


class TimelineParams(BaseModel):
    timeline_type: str = "home"
    username: Optional[str] = None
    limit: Optional[int] = None
    offset: Optional[int] = None


class SearchParams(BaseModel):
    query: str
    limit: Optional[int] = None
    offset: Optional[int] = None


# Health check


@app.get("/")
async def root():
    """API root endpoint."""
    return {
        "service": "FreeFeed API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        client = await get_client()
        return {"status": "healthy", "authenticated": client.auth_token is not None}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@app.post("/api/session", response_model=SessionResponse)
async def create_session(payload: SessionCreate) -> SessionResponse:
    """Create a server-side session using FreeFeed credentials."""
    client: Optional[FreeFeedClient] = None
    try:
        client = await _create_client_from_credentials(
            auth_token=payload.auth_token,
            username=payload.username,
            password=payload.password,
            base_url=payload.base_url,
            api_version=payload.api_version,
        )
        user = await client.whoami()
        if not client.auth_token:
            raise HTTPException(status_code=401, detail="FreeFeed auth failed")
        session_token = str(uuid.uuid4())
        session = SessionData(
            auth_token=client.auth_token,
            base_url=client.base_url,
            api_version=client.api_version,
            username=payload.username,
        )
        async with SESSION_LOCK:
            SESSION_STORE[session_token] = session
        return SessionResponse(session_token=session_token, user=user)
    except HTTPException:
        raise
    except FreeFeedAuthError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))
    finally:
        if client is not None:
            with contextlib.suppress(Exception):
                await client.close()


@app.post("/api/assistant", response_model=AssistantResponse)
async def assistant(payload: AssistantRequest, request: Request) -> AssistantResponse:
    """AI assistant endpoint backed by PydanticAI."""
    try:
        client = await _get_client_for_request(request)
        return await run_assistant(payload, client)
    except FreeFeedAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Timeline endpoints


@app.get("/api/timeline")
async def get_timeline(
    timeline_type: str = "home",
    username: Optional[str] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    request: Request = None,
):
    """Get timeline feed."""
    try:
        client = await _get_client_for_request(request)
        result = await client.get_timeline(
            username=username, timeline_type=timeline_type, limit=limit, offset=offset
        )
        return _add_post_urls(result, client.base_url)
    except FreeFeedAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Post endpoints


@app.get("/api/posts/{post_id}")
async def get_post(post_id: str, request: Request):
    """Get a specific post."""
    try:
        client = await _get_client_for_request(request)
        result = await client.get_post(post_id)
        return _add_post_urls(result, client.base_url)
    except FreeFeedAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/posts")
async def create_post(
    body: Annotated[str, Form(...)],
    group_names: Annotated[Optional[str], Form()] = None,
    files: Annotated[Optional[List[UploadFile]], File()] = None,
    request: Request = None,
):
    """Create a new post with optional files and group posting."""
    try:
        client = await _get_client_for_request(request)

        # Parse group names if provided
        groups = group_names.split(",") if group_names else None

        # Handle file uploads
        attachment_ids = []
        if files:
            for file in files:
                file_data = await file.read()
                result = await client.upload_attachment(
                    file_path=file.filename, file_data=file_data, filename=file.filename
                )
                # Extract attachment ID
                if "attachments" in result:
                    att = result["attachments"]
                    if isinstance(att, dict):
                        attachment_ids.append(att.get("id"))

        # Create post
        result = await client.create_post(
            body=body,
            attachments=attachment_ids if attachment_ids else None,
            group_names=groups,
        )
        return _add_post_urls(result, client.base_url)
    except FreeFeedAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/posts/{post_id}")
async def update_post(post_id: str, data: PostUpdate, request: Request):
    """Update a post."""
    try:
        client = await _get_client_for_request(request)
        result = await client.update_post(post_id, data.body)
        return _add_post_urls(result, client.base_url)
    except FreeFeedAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/posts/{post_id}")
async def delete_post(post_id: str, request: Request):
    """Delete a post."""
    try:
        client = await _get_client_for_request(request)
        result = await client.delete_post(post_id)
        return result
    except FreeFeedAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/posts/{post_id}/like")
async def like_post(post_id: str, request: Request):
    """Like a post."""
    try:
        client = await _get_client_for_request(request)
        result = await client.like_post(post_id)
        return result
    except FreeFeedAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/posts/{post_id}/unlike")
async def unlike_post(post_id: str, request: Request):
    """Unlike a post."""
    try:
        client = await _get_client_for_request(request)
        result = await client.unlike_post(post_id)
        return result
    except FreeFeedAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Attachment endpoints


@app.post("/api/attachments")
async def upload_attachment(file: Annotated[UploadFile, File(...)], request: Request):
    """Upload an attachment."""
    try:
        client = await _get_client_for_request(request)
        file_data = await file.read()
        result = await client.upload_attachment(
            file_path=file.filename, file_data=file_data, filename=file.filename
        )
        return result
    except FreeFeedAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/posts/{post_id}/attachments")
async def get_post_attachments(post_id: str, request: Request):
    """Get attachments for a post."""
    try:
        client = await _get_client_for_request(request)
        post_data = await client.get_post(post_id)

        attachments = []
        if "attachments" in post_data:
            att_list = post_data["attachments"]
            if isinstance(att_list, dict):
                att_list = [att_list]

            for att in att_list:
                attachment_info = {
                    "id": att.get("id"),
                    "fileName": att.get("fileName"),
                    "fileSize": att.get("fileSize"),
                    "mediaType": att.get("mediaType"),
                    "url": client.get_attachment_url(att, "original"),
                    "thumbnailUrl": client.get_attachment_url(att, "thumbnail"),
                }
                attachment_info = {
                    k: v for k, v in attachment_info.items() if v is not None
                }
                attachments.append(attachment_info)

        return {
            "post_id": post_id,
            "attachments": attachments,
            "count": len(attachments),
        }
    except FreeFeedAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/attachments/download")
async def download_attachment(url: str, request: Request):
    """Download an attachment by URL."""
    try:
        client = await _get_client_for_request(request)
        file_data = await client.download_attachment(url)

        # Return as streaming response
        return StreamingResponse(
            io.BytesIO(file_data), media_type="application/octet-stream"
        )
    except FreeFeedAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Comment endpoints


@app.post("/api/posts/{post_id}/comments")
async def add_comment(post_id: str, data: CommentCreate, request: Request):
    """Add a comment to a post."""
    try:
        client = await _get_client_for_request(request)
        result = await client.add_comment(post_id, data.body)
        return result
    except FreeFeedAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/comments/{comment_id}")
async def update_comment(comment_id: str, data: CommentCreate, request: Request):
    """Update a comment."""
    try:
        client = await _get_client_for_request(request)
        result = await client.update_comment(comment_id, data.body)
        return result
    except FreeFeedAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/comments/{comment_id}")
async def delete_comment(comment_id: str, request: Request):
    """Delete a comment."""
    try:
        client = await _get_client_for_request(request)
        result = await client.delete_comment(comment_id)
        return result
    except FreeFeedAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Search endpoints


@app.get("/api/search")
async def search_posts(
    query: str,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    request: Request = None,
):
    """Search posts."""
    try:
        client = await _get_client_for_request(request)
        result = await client.search_posts(query, limit, offset)
        return _add_post_urls(result, client.base_url)
    except FreeFeedAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


# User endpoints


@app.get("/api/users/{username}")
async def get_user_profile(username: str, request: Request):
    """Get user profile."""
    try:
        client = await _get_client_for_request(request)
        result = await client.get_user_profile(username)
        return result
    except FreeFeedAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/users/me")
async def whoami(compact: bool = False, request: Request = None):
    """Get current authenticated user."""
    try:
        client = await _get_client_for_request(request)
        result = await client.whoami()
        if compact:
            result = _compact_whoami(result)
        return result
    except FreeFeedAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/users/{username}/subscribers")
async def get_subscribers(username: str, request: Request):
    """Get user's subscribers."""
    try:
        client = await _get_client_for_request(request)
        result = await client.get_subscribers(username)
        return result
    except FreeFeedAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/users/{username}/subscriptions")
async def get_subscriptions(username: str, request: Request):
    """Get user's subscriptions."""
    try:
        client = await _get_client_for_request(request)
        result = await client.get_subscriptions(username)
        return result
    except FreeFeedAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/users/{username}/subscribe")
async def subscribe_user(username: str, request: Request):
    """Subscribe to a user."""
    try:
        client = await _get_client_for_request(request)
        result = await client.subscribe_user(username)
        return result
    except FreeFeedAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/users/{username}/unsubscribe")
async def unsubscribe_user(username: str, request: Request):
    """Unsubscribe from a user."""
    try:
        client = await _get_client_for_request(request)
        result = await client.unsubscribe_user(username)
        return result
    except FreeFeedAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Group endpoints


@app.get("/api/groups/my")
async def get_my_groups(request: Request):
    """Get list of groups user is member of."""
    try:
        client = await _get_client_for_request(request)
        result = await client.get_my_groups()
        return result
    except FreeFeedAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/groups/{group_name}")
async def get_group_info(group_name: str, request: Request):
    """Get information about a group."""
    try:
        client = await _get_client_for_request(request)
        result = await client.get_group_info(group_name)
        return result
    except FreeFeedAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/groups/{group_name}/timeline")
async def get_group_timeline(
    group_name: str,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    request: Request = None,
):
    """Get timeline for a group."""
    try:
        client = await _get_client_for_request(request)
        result = await client.get_group_timeline(group_name, limit, offset)
        return result
    except FreeFeedAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import sys
    from pathlib import Path

    import uvicorn

    # Check for --ssl flag
    use_ssl = "--ssl" in sys.argv or "--https" in sys.argv

    # Different ports for HTTP and HTTPS
    port = 8443 if use_ssl else 8000

    ssl_config = {}
    if use_ssl:
        cert_dir = Path(__file__).parent.parent / "certs"
        cert_file = cert_dir / "cert.pem"
        key_file = cert_dir / "key.pem"

        if not cert_file.exists() or not key_file.exists():
            print("❌ SSL certificates not found!")
            print(f"   Expected location: {cert_dir}")
            print("")
            print("Run the certificate generation script:")
            print("   ./generate_cert.sh (Linux/macOS)")
            print("   .\\generate_cert.ps1 (Windows)")
            print("")
            sys.exit(1)

        ssl_config = {
            "ssl_keyfile": str(key_file),
            "ssl_certfile": str(cert_file),
        }

        print("🔐 Starting API server with HTTPS")
        print(f"   Certificate: {cert_file}")
        print(f"   Key: {key_file}")
        print("")
        print(f"🌐 HTTPS server available at: https://localhost:{port}")
        print(f"📚 Docs: https://localhost:{port}/docs")
        print("")
    else:
        print("⚠️  Starting API server with HTTP (development only)")
        print("")
        print("Use HTTPS for Claude Desktop:")
        print("   python -m freefeed_mcp_server.api --ssl")
        print("")
        print(f"🌐 HTTP server available at: http://localhost:{port}")
        print(f"📚 Docs: http://localhost:{port}/docs")
        print("")

    uvicorn.run(app, host="0.0.0.0", port=port, **ssl_config)
