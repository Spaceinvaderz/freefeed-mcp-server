# FreeFeed REST API

REST API for accessing FreeFeed over HTTP. Built with FastAPI.

## 🚀 Start the API server

### Quick start

```bash
# Install dependencies
pip install -e .

# Create .env
cat > .env << EOF
FREEFEED_BASE_URL=https://freefeed.net
FREEFEED_API_VERSION=4
FREEFEED_APP_TOKEN=your_app_token
# or
FREEFEED_USERNAME=your_username
FREEFEED_PASSWORD=your_password
EOF

# Run API server
python -m freefeed_mcp_server.api
```

The server will start on `http://localhost:8000`

### Run with uvicorn

```bash
uvicorn freefeed_mcp_server.api:app --reload --host 0.0.0.0 --port 8000
```

### Production run

```bash
uvicorn freefeed_mcp_server.api:app --workers 4 --host 0.0.0.0 --port 8000
```

## 📚 API documentation

After the server starts, interactive docs are available:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## 🔌 Endpoints

### Health check

```bash
# Status check
curl http://localhost:8000/health
```

### Timeline

```bash
# Home feed
curl http://localhost:8000/api/timeline

# User posts
curl "http://localhost:8000/api/timeline?timeline_type=posts&username=someuser&limit=20"

# User likes
curl "http://localhost:8000/api/timeline?timeline_type=likes&username=someuser"
```

### Posts

```bash
# Get a post
curl http://localhost:8000/api/posts/POST_ID

# Create a post
curl -X POST http://localhost:8000/api/posts \
  -F "body=Hello, FreeFeed!" \
  -F "group_names=mygroup,anothergroup"

# Create a post with an image
curl -X POST http://localhost:8000/api/posts \
  -F "body=Check out this photo!" \
  -F "files=@/path/to/image.jpg"

# Create a post with multiple images to a group
curl -X POST http://localhost:8000/api/posts \
  -F "body=Photo report!" \
  -F "files=@photo1.jpg" \
  -F "files=@photo2.jpg" \
  -F "group_names=mygroup"

# Update a post
curl -X PUT http://localhost:8000/api/posts/POST_ID \
  -H "Content-Type: application/json" \
  -d '{"body": "Updated text"}'

# Delete a post
curl -X DELETE http://localhost:8000/api/posts/POST_ID

# Like a post
curl -X POST http://localhost:8000/api/posts/POST_ID/like

# Unlike a post
curl -X POST http://localhost:8000/api/posts/POST_ID/unlike
```

### Attachments

```bash
# Upload a file
curl -X POST http://localhost:8000/api/attachments \
  -F "file=@/path/to/image.jpg"

# Get post attachments
curl http://localhost:8000/api/posts/POST_ID/attachments

# Download an attachment
curl "http://localhost:8000/api/attachments/download?url=https://freefeed.net/attachments/att-id" \
  -o downloaded.jpg
```

### Comments

```bash
# Add a comment
curl -X POST http://localhost:8000/api/posts/POST_ID/comments \
  -H "Content-Type: application/json" \
  -d '{"body": "Great post!"}'

# Update a comment
curl -X PUT http://localhost:8000/api/comments/COMMENT_ID \
  -H "Content-Type: application/json" \
  -d '{"body": "Fixed comment"}'

# Delete a comment
curl -X DELETE http://localhost:8000/api/comments/COMMENT_ID
```

### Search

```bash
# Search posts
curl "http://localhost:8000/api/search?query=MCP"

# Search with operators
curl "http://localhost:8000/api/search?query=intitle:Python%20from:username"

# With pagination
curl "http://localhost:8000/api/search?query=FreeFeed&limit=20&offset=20"
```

### Users

```bash
# Get user profile
curl http://localhost:8000/api/users/username

# Get current user
curl http://localhost:8000/api/users/me

# Get current user (compact response)
curl "http://localhost:8000/api/users/me?compact=true"

# Get subscribers
curl http://localhost:8000/api/users/username/subscribers

# Get subscriptions
curl http://localhost:8000/api/users/username/subscriptions

# Subscribe to a user
curl -X POST http://localhost:8000/api/users/username/subscribe

# Unsubscribe from a user
curl -X POST http://localhost:8000/api/users/username/unsubscribe
```

### Groups

```bash
# Get my groups
curl http://localhost:8000/api/groups/my

# Group info
curl http://localhost:8000/api/groups/mygroup

# Group posts
curl "http://localhost:8000/api/groups/mygroup/timeline?limit=30"
```

## 💻 Usage examples

### Python (requests)

```python
import requests

BASE_URL = "http://localhost:8000"

# Get home feed
response = requests.get(f"{BASE_URL}/api/timeline")
timeline = response.json()
print(f"Posts: {len(timeline.get('posts', []))}")

# Create a post
response = requests.post(
    f"{BASE_URL}/api/posts",
    data={"body": "Hello from Python!"}
)
post = response.json()
print(f"Created post: {post}")

# Create a post with an image
with open("photo.jpg", "rb") as f:
    response = requests.post(
        f"{BASE_URL}/api/posts",
        data={"body": "Photo from Python!"},
        files={"files": f}
    )

# Search
response = requests.get(
    f"{BASE_URL}/api/search",
    params={"query": "Python", "limit": 10}
)
results = response.json()
```

### JavaScript (fetch)

```javascript
const BASE_URL = "http://localhost:8000";

// Get home feed
const timeline = await fetch(`${BASE_URL}/api/timeline`);
const data = await timeline.json();
console.log(`Posts: ${data.posts?.length}`);

// Create a post
const response = await fetch(`${BASE_URL}/api/posts`, {
  method: "POST",
  body: new URLSearchParams({
    body: "Hello from JavaScript!"
  })
});
const post = await response.json();

// Create a post with an image
const formData = new FormData();
formData.append("body", "Photo from JavaScript!");
formData.append("files", fileInput.files[0]);

await fetch(`${BASE_URL}/api/posts`, {
  method: "POST",
  body: formData
});

// Search
const searchResults = await fetch(
  `${BASE_URL}/api/search?query=JavaScript&limit=10`
);
const results = await searchResults.json();
```

### curl + jq (JSON processing)

```bash
# Get names of all groups
curl -s http://localhost:8000/api/groups/my | jq -r '.groups[].username'

# Get recent post titles
curl -s http://localhost:8000/api/timeline | jq -r '.posts[].body' | head -5

# Search and print results
curl -s "http://localhost:8000/api/search?query=MCP" | jq '.posts[] | {id, body}'
```

## 🔐 Security

### CORS

To use from a browser, add the CORS middleware:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Use specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Authentication

The API uses credentials from environment variables. For multi-user API add:

1. JWT tokens
2. API keys
3. OAuth2

## 🚢 Deploy

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install -e .

ENV FREEFEED_BASE_URL=https://freefeed.net
ENV FREEFEED_APP_TOKEN=your_app_token

EXPOSE 8000

CMD ["uvicorn", "freefeed_mcp_server.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t freefeed-api .
docker run -p 8000:8000 --env-file .env freefeed-api
```

### systemd service

```ini
[Unit]
Description=FreeFeed API Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/freefeed-api
EnvironmentFile=/opt/freefeed-api/.env
ExecStart=/usr/local/bin/uvicorn freefeed_mcp_server.api:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

## 📊 Monitoring

### Health check

```bash
# Simple check
curl http://localhost:8000/health

# With monitoring
watch -n 5 'curl -s http://localhost:8000/health | jq'
```

### Logs

```bash
# Run with verbose logs
uvicorn freefeed_mcp_server.api:app --log-level debug
```

## 🎯 Performance

- FastAPI is async and supports many concurrent requests
- Use httpx connection pooling
- Cache frequently requested data
- Use Redis for sessions

## 📝 Swagger UI

After startup, open http://localhost:8000/docs

You will find:
- Interactive documentation for all endpoints
- Ability to test the API in the browser
- Auto-generated request/response examples
- Data schemas

## 🔗 Integrations

The API can be used from:
- Mobile apps (iOS/Android)
- Web apps (React/Vue/Angular)
- Desktop apps (Electron)
- CLI tools
- Zapier/IFTTT webhooks
- Other services over HTTP
