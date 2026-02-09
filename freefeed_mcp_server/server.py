"""FreeFeed MCP Server - provides FreeFeed API access via MCP protocol."""

import asyncio
import base64
import contextlib
import json
import logging
import os
import signal
from mimetypes import guess_type
from typing import Any

import mcp.server.stdio
from dotenv import load_dotenv
from mcp.server import Server
from mcp.types import ImageContent, TextContent, Tool

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

DEFAULT_OPT_OUT_TAGS = ["#noai", "#opt-out-ai", "#no-bots", "#ai-free"]
FILTER_REASON = "User opted out of AI interactions"
DEFAULT_IMAGE_MAX_BYTES = 2_000_000


def _parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def _resolve_image_max_bytes() -> int:
    raw = os.getenv("FREEFEED_MCP_IMAGE_MAX_BYTES", str(DEFAULT_IMAGE_MAX_BYTES))
    try:
        value = int(raw)
        return max(256_000, value)
    except ValueError:
        return DEFAULT_IMAGE_MAX_BYTES


def _load_opt_out_config() -> dict:
    config = {
        "enabled": False,
        "users": set(),
        "tags": list(DEFAULT_OPT_OUT_TAGS),
        "respect_private": True,
        "respect_paused": True,
    }

    config_path = os.getenv("FREEFEED_OPTOUT_CONFIG")
    if config_path:
        try:
            with open(config_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                if isinstance(data.get("enabled"), bool):
                    config["enabled"] = data["enabled"]
                if isinstance(data.get("manual_opt_out"), list):
                    config["users"] = {
                        str(u).strip() for u in data["manual_opt_out"] if str(u).strip()
                    }
                if isinstance(data.get("tags"), list):
                    config["tags"] = [
                        str(t).strip() for t in data["tags"] if str(t).strip()
                    ]
                if isinstance(data.get("respect_private"), bool):
                    config["respect_private"] = data["respect_private"]
                if isinstance(data.get("respect_paused"), bool):
                    config["respect_paused"] = data["respect_paused"]
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read opt-out config %s: %s", config_path, exc)

    enabled_env = _parse_bool(os.getenv("FREEFEED_OPTOUT_ENABLED"))
    if enabled_env is not None:
        config["enabled"] = enabled_env

    users_env = os.getenv("FREEFEED_OPTOUT_USERS")
    if users_env is not None:
        config["users"] = {u.strip() for u in users_env.split(",") if u.strip()}

    tags_env = os.getenv("FREEFEED_OPTOUT_TAGS")
    if tags_env is not None:
        config["tags"] = [t.strip() for t in tags_env.split(",") if t.strip()]

    respect_private_env = _parse_bool(os.getenv("FREEFEED_OPTOUT_RESPECT_PRIVATE"))
    if respect_private_env is not None:
        config["respect_private"] = respect_private_env

    respect_paused_env = _parse_bool(os.getenv("FREEFEED_OPTOUT_RESPECT_PAUSED"))
    if respect_paused_env is not None:
        config["respect_paused"] = respect_paused_env

    return config


def _configure_server_logger() -> None:
    """Ensure server logs are also written to a file."""
    default_path = os.path.join(".", "logs", "freefeed_server.log")
    log_path = os.getenv("FREEFEED_SERVER_LOG_PATH", default_path).strip()
    if not log_path:
        return

    log_path = os.path.abspath(os.path.expanduser(log_path))
    log_dir = os.path.dirname(log_path)
    if log_dir:
        try:
            os.makedirs(log_dir, exist_ok=True)
        except OSError as exc:
            logger.warning("Could not create log directory %s: %s", log_dir, exc)
            return

    for handler in logger.handlers:
        if (
            isinstance(handler, logging.FileHandler)
            and os.path.abspath(handler.baseFilename) == log_path
        ):
            return

    try:
        file_handler = logging.FileHandler(log_path)
    except OSError as exc:
        logger.warning("Could not open log file %s: %s", log_path, exc)
        return

    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    file_handler.setLevel(_resolve_log_level())
    logger.addHandler(file_handler)


_configure_server_logger()

# Initialize MCP server
app = Server("freefeed-mcp-server")

# Global client instance
freefeed_client: FreeFeedClient | None = None


async def get_client() -> FreeFeedClient:
    """Get or create FreeFeed client instance."""
    global freefeed_client

    if freefeed_client is None:
        base_url = os.getenv("FREEFEED_BASE_URL", "https://freefeed.net")
        api_version_raw = os.getenv("FREEFEED_API_VERSION")
        app_token = os.getenv("FREEFEED_APP_TOKEN")
        username = os.getenv("FREEFEED_USERNAME")
        password = os.getenv("FREEFEED_PASSWORD")

        api_version: int | None = None
        if api_version_raw:
            try:
                api_version = int(api_version_raw)
            except ValueError:
                logger.warning(
                    "Invalid FREEFEED_API_VERSION=%s; using default", api_version_raw
                )

        if not app_token and (not username or not password):
            raise FreeFeedAuthError(
                "Set FREEFEED_APP_TOKEN or FREEFEED_USERNAME and FREEFEED_PASSWORD"
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
            await freefeed_client.authenticate()
            logger.info("FreeFeed client initialized and authenticated")

    return freefeed_client


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


def _add_post_urls(payload: Any, base_url: str) -> Any:
    if not isinstance(payload, dict):
        return payload

    users = payload.get("users")
    user_map: dict[str, str] = {}
    if isinstance(users, list):
        for user in users:
            if isinstance(user, dict) and user.get("id") and user.get("username"):
                user_map[user["id"]] = user["username"]

    def _apply(post: dict) -> None:
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

    posts = payload.get("posts")
    if isinstance(posts, list):
        for post in posts:
            if isinstance(post, dict):
                _apply(post)
    elif isinstance(posts, dict):
        _apply(posts)

    return payload


async def _fetch_attachment_data(
    client: FreeFeedClient, attachment_url: str, max_bytes: int
) -> tuple[bytes | None, str | None, int | None, str | None]:
    content_type: str | None = None
    content_length: int | None = None
    headers: dict[str, str] = {}
    if client.auth_token:
        headers["X-Authentication-Token"] = client.auth_token

    try:
        head = await client.client.head(attachment_url, headers=headers)
        if head.status_code < 400:
            content_type = head.headers.get("content-type")
            length_header = head.headers.get("content-length")
            if length_header and length_header.isdigit():
                content_length = int(length_header)
    except Exception:
        pass

    if content_length is not None and content_length > max_bytes:
        return None, content_type, content_length, "too_large"

    response = await client.client.get(attachment_url, headers=headers)
    response.raise_for_status()
    if content_type is None:
        content_type = response.headers.get("content-type")
    data = response.content
    if len(data) > max_bytes:
        return None, content_type, len(data), "too_large"

    if content_type is None:
        content_type = guess_type(attachment_url)[0]

    return data, content_type, len(data), None


def should_skip_user(username: str, user_profile: dict) -> bool:
    """Return True if a user's content should be excluded from AI analysis."""
    config = _load_opt_out_config()
    if not config["enabled"]:
        return False

    if username in config["users"]:
        return True

    if config["respect_paused"] and user_profile.get("isGone") is True:
        return True

    if config["respect_private"] and user_profile.get("isPrivate") == "1":
        return True

    description = str(user_profile.get("description", "")).lower()
    return any(tag in description for tag in config["tags"])


def _build_user_map(payload: dict) -> dict[str, dict]:
    users = payload.get("users")
    if isinstance(users, dict):
        if users.get("id"):
            return {users["id"]: users}
        return {}

    if isinstance(users, list):
        return {
            user["id"]: user
            for user in users
            if isinstance(user, dict) and user.get("id")
        }

    return {}


def _filter_posts_payload(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload

    config = _load_opt_out_config()
    if not config["enabled"]:
        return payload

    posts = payload.get("posts")
    if not isinstance(posts, list):
        return payload

    user_map = _build_user_map(payload)
    kept_posts = []
    filtered_users: set[str] = set()
    removed_post_ids: set[str] = set()

    for post in posts:
        if not isinstance(post, dict):
            continue
        author_id = post.get("createdBy")
        user_profile = user_map.get(author_id, {})
        username = (
            user_profile.get("username") if isinstance(user_profile, dict) else None
        )

        if username and should_skip_user(username, user_profile):
            filtered_users.add(username)
            post_id = post.get("id")
            if post_id:
                removed_post_ids.add(post_id)
            continue

        kept_posts.append(post)

    payload["posts"] = kept_posts

    if removed_post_ids:
        timelines = payload.get("timelines")
        if isinstance(timelines, dict) and isinstance(timelines.get("posts"), list):
            timelines["posts"] = [
                post_id
                for post_id in timelines["posts"]
                if post_id not in removed_post_ids
            ]

        comments = payload.get("comments")
        if isinstance(comments, list):
            payload["comments"] = [
                comment
                for comment in comments
                if isinstance(comment, dict)
                and comment.get("postId") not in removed_post_ids
            ]

        attachments = payload.get("attachments")
        if isinstance(attachments, list):
            payload["attachments"] = [
                attachment
                for attachment in attachments
                if isinstance(attachment, dict)
                and attachment.get("postId") not in removed_post_ids
            ]

        payload["filtered_users"] = sorted(filtered_users)
        payload["filter_reason"] = FILTER_REASON

    return payload


# Tool definitions


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available FreeFeed tools."""
    return [
        # Timeline tools
        Tool(
            name="get_timeline",
            description=(
                "Get timeline feed from FreeFeed. Can get home feed, user posts, "
                "user likes, user comments, or discussions feed. "
                "Timeline types: 'home', 'posts', 'likes', 'comments', 'discussions'"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "timeline_type": {
                        "type": "string",
                        "enum": ["home", "posts", "likes", "comments", "discussions"],
                        "description": "Type of timeline to retrieve",
                        "default": "home",
                    },
                    "username": {
                        "type": "string",
                        "description": "Username (required for posts/likes/comments timelines)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of posts to return",
                        "minimum": 1,
                        "maximum": 100,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Offset for pagination",
                        "minimum": 0,
                    },
                },
                "required": ["timeline_type"],
            },
        ),
        # Post tools
        Tool(
            name="get_post",
            description="Get a specific post by ID with all comments",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "Post ID",
                    },
                },
                "required": ["post_id"],
            },
        ),
        Tool(
            name="create_post",
            description="Create a new post on FreeFeed with optional file attachments and optional group posting",
            inputSchema={
                "type": "object",
                "properties": {
                    "body": {
                        "type": "string",
                        "description": "Post text content",
                    },
                    "attachment_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of file paths to attach (will be uploaded automatically)",
                    },
                    "group_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of group usernames to post to (e.g., ['mygroup', 'anothergroup'])",
                    },
                },
                "required": ["body"],
            },
        ),
        Tool(
            name="update_post",
            description="Update an existing post",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "Post ID to update",
                    },
                    "body": {
                        "type": "string",
                        "description": "New post text content",
                    },
                },
                "required": ["post_id", "body"],
            },
        ),
        Tool(
            name="delete_post",
            description="Delete a post",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "Post ID to delete",
                    },
                },
                "required": ["post_id"],
            },
        ),
        Tool(
            name="like_post",
            description="Like a post",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "Post ID to like",
                    },
                },
                "required": ["post_id"],
            },
        ),
        Tool(
            name="unlike_post",
            description="Remove like from a post",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "Post ID to unlike",
                    },
                },
                "required": ["post_id"],
            },
        ),
        Tool(
            name="hide_post",
            description="Hide a post from your feed",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "Post ID to hide",
                    },
                },
                "required": ["post_id"],
            },
        ),
        Tool(
            name="unhide_post",
            description="Unhide a previously hidden post",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "Post ID to unhide",
                    },
                },
                "required": ["post_id"],
            },
        ),
        # Attachment tools
        Tool(
            name="upload_attachment",
            description="Upload a file attachment (image, video, etc.) to FreeFeed. Returns attachment ID that can be used in posts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to upload",
                    },
                },
                "required": ["file_path"],
            },
        ),
        Tool(
            name="download_attachment",
            description=(
                "Download an attachment from a FreeFeed post. If the file is an image and "
                "small enough, returns image content plus a URL fallback; otherwise returns a URL. "
                "Can also save to file."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "attachment_url": {
                        "type": "string",
                        "description": "URL of the attachment to download (from post/comment data)",
                    },
                    "save_path": {
                        "type": "string",
                        "description": "Optional path to save file. If not provided, returns base64-encoded data.",
                    },
                    "prefer_image": {
                        "type": "boolean",
                        "description": "Return image content when possible",
                        "default": True,
                    },
                    "max_bytes": {
                        "type": "integer",
                        "description": "Maximum bytes to return for inline image data",
                        "minimum": 256000,
                    },
                },
                "required": ["attachment_url"],
            },
        ),
        Tool(
            name="get_attachment_image",
            description=(
                "Download an attachment and return image content when possible. "
                "Returns image content plus a URL fallback; for large files, returns only the URL."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "attachment_url": {
                        "type": "string",
                        "description": "URL of the attachment to download (from post/comment data)",
                    },
                    "max_bytes": {
                        "type": "integer",
                        "description": "Maximum bytes to return for inline image data",
                        "minimum": 256000,
                    },
                },
                "required": ["attachment_url"],
            },
        ),
        Tool(
            name="get_post_attachments",
            description="Extract attachment URLs and metadata from a post. Returns list of attachments with URLs for downloading.",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "Post ID to get attachments from",
                    },
                },
                "required": ["post_id"],
            },
        ),
        # Comment tools
        Tool(
            name="add_comment",
            description="Add a comment to a post",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {
                        "type": "string",
                        "description": "Post ID to comment on",
                    },
                    "body": {
                        "type": "string",
                        "description": "Comment text",
                    },
                },
                "required": ["post_id", "body"],
            },
        ),
        Tool(
            name="update_comment",
            description="Update an existing comment",
            inputSchema={
                "type": "object",
                "properties": {
                    "comment_id": {
                        "type": "string",
                        "description": "Comment ID to update",
                    },
                    "body": {
                        "type": "string",
                        "description": "New comment text",
                    },
                },
                "required": ["comment_id", "body"],
            },
        ),
        Tool(
            name="delete_comment",
            description="Delete a comment",
            inputSchema={
                "type": "object",
                "properties": {
                    "comment_id": {
                        "type": "string",
                        "description": "Comment ID to delete",
                    },
                },
                "required": ["comment_id"],
            },
        ),
        # Search tools
        Tool(
            name="search_posts",
            description=(
                "Search posts on FreeFeed. Supports search operators: "
                "intitle:query (search in post text), "
                "incomment:query (search in comments), "
                "from:username (search by author), "
                "AND/OR (logical operators)"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query with optional operators",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of results to return",
                        "minimum": 1,
                        "maximum": 100,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Offset for pagination",
                        "minimum": 0,
                    },
                },
                "required": ["query"],
            },
        ),
        # User tools
        Tool(
            name="get_user_profile",
            description="Get user profile information",
            inputSchema={
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Username to get profile for",
                    },
                },
                "required": ["username"],
            },
        ),
        Tool(
            name="whoami",
            description="Get current authenticated user information",
            inputSchema={
                "type": "object",
                "properties": {
                    "compact": {
                        "type": "boolean",
                        "description": "Return a compact response to avoid large payloads",
                        "default": False,
                    }
                },
            },
        ),
        Tool(
            name="get_subscribers",
            description="Get list of user's subscribers (followers)",
            inputSchema={
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Username to get subscribers for",
                    },
                },
                "required": ["username"],
            },
        ),
        Tool(
            name="get_subscriptions",
            description="Get list of user's subscriptions (following)",
            inputSchema={
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Username to get subscriptions for",
                    },
                },
                "required": ["username"],
            },
        ),
        Tool(
            name="subscribe_user",
            description="Subscribe to (follow) a user",
            inputSchema={
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Username to subscribe to",
                    },
                },
                "required": ["username"],
            },
        ),
        Tool(
            name="unsubscribe_user",
            description="Unsubscribe from (unfollow) a user",
            inputSchema={
                "type": "object",
                "properties": {
                    "username": {
                        "type": "string",
                        "description": "Username to unsubscribe from",
                    },
                },
                "required": ["username"],
            },
        ),
        # Group tools
        Tool(
            name="get_my_groups",
            description="Get list of groups that current user is a member of",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="get_group_timeline",
            description="Get posts from a specific group",
            inputSchema={
                "type": "object",
                "properties": {
                    "group_name": {
                        "type": "string",
                        "description": "Group username/name",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of posts to return",
                        "minimum": 1,
                        "maximum": 100,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Offset for pagination",
                        "minimum": 0,
                    },
                },
                "required": ["group_name"],
            },
        ),
        Tool(
            name="get_group_info",
            description="Get information about a specific group",
            inputSchema={
                "type": "object",
                "properties": {
                    "group_name": {
                        "type": "string",
                        "description": "Group username/name",
                    },
                },
                "required": ["group_name"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent | ImageContent]:
    """Handle tool calls."""
    try:
        client = await get_client()

        # Timeline tools
        if name == "get_timeline":
            result = await client.get_timeline(
                username=arguments.get("username"),
                timeline_type=arguments.get("timeline_type", "home"),
                limit=arguments.get("limit"),
                offset=arguments.get("offset"),
            )
            result = _filter_posts_payload(result)

        # Post tools
        elif name == "get_post":
            result = await client.get_post(arguments["post_id"])
            user_map = _build_user_map(result)
            post = result.get("posts") if isinstance(result, dict) else None
            if isinstance(post, dict):
                author_id = post.get("createdBy")
                user_profile = user_map.get(author_id, {})
                username = (
                    user_profile.get("username")
                    if isinstance(user_profile, dict)
                    else None
                )
                if username and should_skip_user(username, user_profile):
                    result = {
                        "error": "Post author opted out of AI interactions",
                        "filtered_users": [username],
                        "filter_reason": FILTER_REASON,
                    }

        elif name == "create_post":
            attachment_paths = arguments.get("attachment_paths")
            group_names = arguments.get("group_names")
            result = await client.create_post(
                body=arguments["body"],
                attachment_files=attachment_paths if attachment_paths else None,
                group_names=group_names if group_names else None,
            )

        elif name == "update_post":
            result = await client.update_post(
                post_id=arguments["post_id"],
                body=arguments["body"],
            )

        elif name == "delete_post":
            result = await client.delete_post(arguments["post_id"])

        elif name == "like_post":
            result = await client.like_post(arguments["post_id"])

        elif name == "unlike_post":
            result = await client.unlike_post(arguments["post_id"])

        elif name == "hide_post":
            result = await client.hide_post(arguments["post_id"])

        elif name == "unhide_post":
            result = await client.unhide_post(arguments["post_id"])

        # Attachment tools
        elif name == "upload_attachment":
            result = await client.upload_attachment(
                file_path=arguments["file_path"],
            )

        elif name == "download_attachment":
            save_path = arguments.get("save_path")
            prefer_image = arguments.get("prefer_image", True)
            max_bytes = arguments.get("max_bytes")
            if not isinstance(max_bytes, int) or max_bytes <= 0:
                max_bytes = _resolve_image_max_bytes()

            if save_path:
                # Download and save to file
                saved_path = await client.download_attachment(
                    attachment_url=arguments["attachment_url"],
                    save_path=save_path,
                )
                result = {
                    "success": True,
                    "saved_to": str(saved_path),
                    "message": f"Attachment downloaded to {saved_path}",
                }
            else:
                attachment_url = arguments["attachment_url"]
                file_data, content_type, size, error = await _fetch_attachment_data(
                    client, attachment_url, max_bytes
                )
                if error == "too_large":
                    result = {
                        "success": False,
                        "message": "Attachment is too large for inline data",
                        "url": attachment_url,
                        "max_bytes": max_bytes,
                        "size": size,
                        "content_type": content_type,
                    }
                elif (
                    prefer_image and content_type and content_type.startswith("image/")
                ):
                    image_content = ImageContent(
                        type="image",
                        data=base64.b64encode(file_data or b"").decode("utf-8"),
                        mimeType=content_type,
                    )
                    text_content = TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "success": True,
                                "message": "Attachment returned as image content",
                                "url": attachment_url,
                                "size": size,
                                "content_type": content_type,
                            },
                            indent=2,
                            ensure_ascii=False,
                        ),
                    )
                    return [image_content, text_content]
                else:
                    result = {
                        "success": True,
                        "data": base64.b64encode(file_data or b"").decode("utf-8"),
                        "size": size,
                        "message": "Attachment downloaded as base64 data",
                        "content_type": content_type,
                        "url": attachment_url,
                    }

        elif name == "get_attachment_image":
            attachment_url = arguments["attachment_url"]
            max_bytes = arguments.get("max_bytes")
            if not isinstance(max_bytes, int) or max_bytes <= 0:
                max_bytes = _resolve_image_max_bytes()

            file_data, content_type, size, error = await _fetch_attachment_data(
                client, attachment_url, max_bytes
            )
            if error == "too_large":
                result = {
                    "success": False,
                    "message": "Attachment is too large for inline image data",
                    "url": attachment_url,
                    "max_bytes": max_bytes,
                    "size": size,
                    "content_type": content_type,
                }
            elif not content_type or not content_type.startswith("image/"):
                result = {
                    "success": False,
                    "message": "Attachment is not an image",
                    "url": attachment_url,
                    "size": size,
                    "content_type": content_type,
                }
            else:
                image_content = ImageContent(
                    type="image",
                    data=base64.b64encode(file_data or b"").decode("utf-8"),
                    mimeType=content_type,
                )
                text_content = TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": True,
                            "message": "Attachment returned as image content",
                            "url": attachment_url,
                            "size": size,
                            "content_type": content_type,
                        },
                        indent=2,
                        ensure_ascii=False,
                    ),
                )
                return [image_content, text_content]

        elif name == "get_post_attachments":
            # Get the post first
            post_data = await client.get_post(arguments["post_id"])

            user_map = _build_user_map(post_data)
            post = post_data.get("posts") if isinstance(post_data, dict) else None
            if isinstance(post, dict):
                author_id = post.get("createdBy")
                user_profile = user_map.get(author_id, {})
                username = (
                    user_profile.get("username")
                    if isinstance(user_profile, dict)
                    else None
                )
                if username and should_skip_user(username, user_profile):
                    result = {
                        "error": "Post author opted out of AI interactions",
                        "filtered_users": [username],
                        "filter_reason": FILTER_REASON,
                    }
                    result = _add_post_urls(result, client.base_url)
                    import json

                    return [
                        TextContent(
                            type="text",
                            text=json.dumps(result, indent=2, ensure_ascii=False),
                        )
                    ]

            # Extract attachments
            attachments = []

            # Check if post has attachments
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
                        "imageSizes": att.get("imageSizes", {}),
                    }
                    # Remove None values
                    attachment_info = {
                        k: v for k, v in attachment_info.items() if v is not None
                    }
                    attachments.append(attachment_info)

            result = {
                "post_id": arguments["post_id"],
                "attachments": attachments,
                "count": len(attachments),
            }

        # Comment tools
        elif name == "add_comment":
            result = await client.add_comment(
                post_id=arguments["post_id"],
                body=arguments["body"],
            )

        elif name == "update_comment":
            result = await client.update_comment(
                comment_id=arguments["comment_id"],
                body=arguments["body"],
            )

        elif name == "delete_comment":
            result = await client.delete_comment(arguments["comment_id"])

        # Search tools
        elif name == "search_posts":
            result = await client.search_posts(
                query=arguments["query"],
                limit=arguments.get("limit"),
                offset=arguments.get("offset"),
            )
            result = _filter_posts_payload(result)

        # User tools
        elif name == "get_user_profile":
            result = await client.get_user_profile(arguments["username"])

        elif name == "whoami":
            result = await client.whoami()
            if arguments.get("compact"):
                result = _compact_whoami(result)

        elif name == "get_subscribers":
            result = await client.get_subscribers(arguments["username"])

        elif name == "get_subscriptions":
            result = await client.get_subscriptions(arguments["username"])

        elif name == "subscribe_user":
            result = await client.subscribe_user(arguments["username"])

        elif name == "unsubscribe_user":
            result = await client.unsubscribe_user(arguments["username"])

        # Group tools
        elif name == "get_my_groups":
            result = await client.get_my_groups()

        elif name == "get_group_timeline":
            result = await client.get_group_timeline(
                group_name=arguments["group_name"],
                limit=arguments.get("limit"),
                offset=arguments.get("offset"),
            )

        elif name == "get_group_info":
            result = await client.get_group_info(arguments["group_name"])

        else:
            raise ValueError(f"Unknown tool: {name}")

        result = _add_post_urls(result, client.base_url)

        # Format result as JSON string
        import json

        return [
            TextContent(
                type="text", text=json.dumps(result, indent=2, ensure_ascii=False)
            )
        ]

    except FreeFeedAPIError as e:
        logger.error(f"FreeFeed API error in {name}: {e}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]
    except Exception as e:
        logger.error(f"Unexpected error in {name}: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Unexpected error: {str(e)}")]


async def main():
    """Run the MCP server."""
    stop_event = asyncio.Event()
    shutdown_started = False

    def _request_shutdown() -> None:
        nonlocal shutdown_started
        if shutdown_started:
            return
        shutdown_started = True
        logger.info("FreeFeed MCP Server shutting down...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(signal.SIGINT, _request_shutdown)
        loop.add_signal_handler(signal.SIGTERM, _request_shutdown)
    except NotImplementedError:
        pass

    try:
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            logger.info("FreeFeed MCP Server starting...")
            run_task = asyncio.create_task(
                app.run(
                    read_stream,
                    write_stream,
                    app.create_initialization_options(),
                )
            )
            stop_task = asyncio.create_task(stop_event.wait())
            done, _ = await asyncio.wait(
                {run_task, stop_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if stop_task in done:
                run_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    try:
                        await asyncio.wait_for(run_task, timeout=2.0)
                    except TimeoutError:
                        logger.warning("Server shutdown timed out; forcing exit")
            else:
                _request_shutdown()
    except KeyboardInterrupt:
        _request_shutdown()
    finally:
        if freefeed_client is not None:
            await freefeed_client.close()
        logger.info("FreeFeed MCP Server shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
