# FreeFeed MCP Server

MCP server for the FreeFeed API, a social network that replaces FriendFeed.

## Features

### Read
- `get_timeline` - Get a user timeline or the home feed
- `get_post` - Get a specific post with comments
- `get_post_attachments` - Get attachment list with URLs
- `search_posts` - Search posts with advanced operators
- `get_user_profile` - Get user profile info
- `get_user_subscriptions` - Get subscriptions/subscribers
- `get_my_groups` - Get user's groups
- `get_group_timeline` - Get group posts
- `get_group_info` - Get group info

### Write
- `upload_attachment` - Upload files (images, video, etc.)
- `download_attachment` - Download post attachments
- `create_post` - Create a new post (auto uploads files, supports posting to groups)
- `update_post` - Edit a post
- `delete_post` - Delete a post
- `like_post` / `unlike_post` - Likes
- `add_comment` - Add a comment
- `update_comment` / `delete_comment` - Manage comments
- `subscribe_user` / `unsubscribe_user` - Subscribe/unsubscribe

## Privacy & Opt-out

Users can opt out of AI analysis by:
1. Adding one of these tags to their profile description: #noai, #opt-out-ai, #no-bots, #ai-free
2. Setting their account to private
3. Contacting the server maintainer to be added to the manual opt-out list

The server automatically excludes:
- Private accounts (isPrivate: "1")
- Paused accounts (isGone: true)
- Users with opt-out tags in their profile

Opt-out filtering is disabled by default. Enable it with configuration:

- `FREEFEED_OPTOUT_ENABLED=true`
- `FREEFEED_OPTOUT_USERS=berkgaut,anotheruser`
- `FREEFEED_OPTOUT_TAGS=#noai,#opt-out-ai,#no-bots,#ai-free`
- `FREEFEED_OPTOUT_RESPECT_PRIVATE=true`
- `FREEFEED_OPTOUT_RESPECT_PAUSED=true`
- `FREEFEED_OPTOUT_CONFIG=/path/to/opt_out.json`

Example opt-out config file:

```json
{
  "enabled": true,
  "manual_opt_out": ["someuser"],
  "tags": ["#noai", "#opt-out-ai", "#no-bots", "#ai-free"],
  "respect_private": true,
  "respect_paused": true
}
```

## Installation

1. Install dependencies:
```bash
pip install -e .
```

2. Create a `.env` file:
```env
FREEFEED_BASE_URL=https://freefeed.net
FREEFEED_API_VERSION=4
FREEFEED_APP_TOKEN=your_app_token
# or
FREEFEED_USERNAME=your_username
FREEFEED_PASSWORD=your_password
```

## Usage

### Start server

```bash
python -m freefeed_mcp_server
```

### REST API server

```bash
# Start HTTP API server
python -m freefeed_mcp_server.api

# Or with uvicorn
uvicorn freefeed_mcp_server.api:app --reload
```

The API will be available at `http://localhost:8000`

📚 **API documentation**: see [API.md](API.md)
🌐 **Swagger UI**: http://localhost:8000/docs

### Claude Desktop integration

Add to Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "freefeed": {
      "command": "python",
      "args": ["-m", "freefeed_mcp_server"],
      "env": {
        "FREEFEED_BASE_URL": "https://freefeed.net",
        "FREEFEED_API_VERSION": "4",
        "FREEFEED_APP_TOKEN": "your_app_token"
      }
    }
  }
}
```

### Claude Desktop integration (system Python)

Use the system Python executable:

```json
{
  "mcpServers": {
    "freefeed": {
      "command": "/usr/bin/python3",
      "args": ["-m", "freefeed_mcp_server"],
      "env": {
        "FREEFEED_BASE_URL": "https://freefeed.net",
        "FREEFEED_API_VERSION": "4",
        "FREEFEED_APP_TOKEN": "your_app_token"
      }
    }
  }
}
```

### Claude Desktop integration (virtualenv)

Use the Python executable from your virtualenv:

```json
{
  "mcpServers": {
    "freefeed": {
      "command": "/path/to/venv/bin/python",
      "args": ["-m", "freefeed_mcp_server"],
      "env": {
        "FREEFEED_BASE_URL": "https://freefeed.net",
        "FREEFEED_API_VERSION": "4",
        "FREEFEED_APP_TOKEN": "your_app_token"
      }
    }
  }
}
```

Replace `/path/to/venv/bin/python` with your actual virtualenv path. On macOS it is often
`./.venv/bin/python` if you created a local venv in the project directory.

## Request examples

### Get home feed
```json
{
  "name": "get_timeline",
  "arguments": {
    "timeline_type": "home"
  }
}
```

### Search posts
```json
{
  "name": "search_posts",
  "arguments": {
    "query": "intitle:MCP from:username"
  }
}
```

### Create a post
```json
{
  "name": "create_post",
  "arguments": {
    "body": "Testing the FreeFeed MCP server!"
  }
}
```

### Create a post with an image
```json
{
  "name": "create_post",
  "arguments": {
    "body": "Check out this photo!",
    "attachment_paths": ["/path/to/image.jpg"]
  }
}
```

### Create a post in a group
```json
{
  "name": "create_post",
  "arguments": {
    "body": "A post for my group!",
    "group_names": ["mygroup"]
  }
}
```

### Get group posts
```json
{
  "name": "get_group_timeline",
  "arguments": {
    "group_name": "mygroup",
    "limit": 20
  }
}
```

### Get post attachments and download
```json
{
  "name": "get_post_attachments",
  "arguments": {
    "post_id": "post-id-here"
  }
}
```

Then download:
```json
{
  "name": "download_attachment",
  "arguments": {
    "attachment_url": "https://freefeed.net/attachments/att-id",
    "save_path": "/path/to/save/image.jpg"
  }
}
```

## FreeFeed API

API docs: https://github.com/FreeFeed/freefeed-server/wiki/API

Supported search operators:
- `intitle:query` - search in post body
- `incomment:query` - search in comments
- `from:username` - search by author
- `AND`, `OR` - logical operators

## License

MIT
