# FreeFeed MCP Server - Quick Start

## 🚀 Install and run in 3 steps

### Step 1: Install dependencies

```bash
cd freefeed-mcp-server
pip install -e .
```

### Step 2: Create a .env file

```bash
cp .env.example .env
```

Edit `.env` and set your values:

```env
FREEFEED_BASE_URL=https://freefeed.net
FREEFEED_API_VERSION=4
FREEFEED_APP_TOKEN=your_app_token
# or
FREEFEED_USERNAME=your_username
FREEFEED_PASSWORD=your_password
```

### Step 3: Start the server

```bash
python -m freefeed_mcp_server
```

## 🔧 Claude Desktop integration

### macOS

Edit the file:
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

### Windows

Edit the file:
```
%APPDATA%\Claude\claude_desktop_config.json
```

### Config content:

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

**Important:** Use the full Python path if needed:
- macOS/Linux: `/usr/local/bin/python3` or `/usr/bin/python3`
- Windows: `C:\Python311\python.exe`

After editing the config, **restart Claude Desktop**.

## ✅ Quick check

After Claude Desktop starts, try:

1. "Show my home feed on FreeFeed"
2. "Create a post on FreeFeed: Hello everyone!"
3. "Find posts about Python on FreeFeed"
4. "Upload ~/Pictures/sunset.jpg and create a post: Beautiful sunset!"

## 📚 Available commands

### Read
- `get_timeline` - Feed (home/posts/likes/comments/discussions)
- `get_post` - Get a post by ID
- `get_post_attachments` - Get post attachments
- `search_posts` - Search posts (supports intitle:, incomment:, from:)
- `get_user_profile` - User profile
- `whoami` - Current user
- `get_subscribers` - Subscribers
- `get_subscriptions` - Subscriptions
- `get_my_groups` - My groups
- `get_group_timeline` - Group posts
- `get_group_info` - Group info

### Write
- `upload_attachment` - Upload a file (image, video, document)
- `download_attachment` - Download a post attachment
- `create_post` - Create a post (uploads files, supports posting to groups)
- `update_post` - Update a post
- `delete_post` - Delete a post
- `like_post` / `unlike_post` - Like/unlike
- `hide_post` / `unhide_post` - Hide/unhide
- `add_comment` - Add a comment
- `update_comment` / `delete_comment` - Edit/delete a comment
- `subscribe_user` / `unsubscribe_user` - Subscribe/unsubscribe

## 🧪 Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# With coverage
pytest --cov=freefeed_mcp_server
```

## 🐛 Debugging

If the server does not work:

1. **Check Claude Desktop logs:**
   - macOS: `~/Library/Logs/Claude/`
   - Windows: `%APPDATA%\Claude\logs\`

2. **Validate credentials:**
   ```bash
   python -c "from freefeed_mcp_server import FreeFeedClient; import asyncio; asyncio.run(FreeFeedClient('https://freefeed.net', 'user', 'pass').authenticate())"
   ```

3. **Enable debug logging:**
   ```bash
   export LOG_LEVEL=DEBUG
   python -m freefeed_mcp_server
   ```

## 📖 Documentation

- **README.md** - Overview
- **EXAMPLES.md** - Detailed examples for all commands
- **API**: https://github.com/FreeFeed/freefeed-server/wiki/API

## 🔐 Security

⚠️ **Do not commit `.env` to git.**

`.gitignore` is already configured to ignore `.env`.

## 📝 Implementation status

✅ **Implemented in v0.1.0:**
- Reading and writing posts
- Attachments upload (images, video, documents)
- Downloading attachments from posts
- Comments
- Search
- Users (subscriptions, profiles)
- Groups (read posts, post to groups)
- Likes
- Timeline (all types)

❌ **Not implemented (planned):**
- Create/delete groups
- Manage group admins
- Ban users
- Update profile/avatar
- Reset password

## 🤝 Contributing

Project is open for contributions. Pull requests are welcome.

## 📄 License

MIT License - see LICENSE
