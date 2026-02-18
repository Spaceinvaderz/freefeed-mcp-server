# Changelog

## [Unreleased]

### Added
- Docker support: Dockerfile with multistage build for optimized image size
- docker-compose.yml for easy deployment and development
- .dockerignore for efficient container builds
- DOCKER.md documentation with quick start and production deployment guides
- Dual HTTP+HTTPS server support: when `FREEFEED_SSL_ENABLED=1`, runs both servers simultaneously
  - HTTP server on port 8000 (configurable via `FREEFEED_API_PORT`)
  - HTTPS server on port 8443 (configurable via `FREEFEED_API_HTTPS_PORT`)
- API mode support in `__main__.py`: can run REST API server in Docker via `FREEFEED_API_MODE=1` env variable
- Docker networking support:
  - `docker-compose.external-network.yml` for sharing network with other compose projects
  - `docker-compose.example-client.yml` example of client service connecting to freefeed-mcp-server
  - `setup-docker-network.sh` helper script to create external shared network
  - Service discovery via DNS name within Docker networks
  - Multiple network support (internal + external), see [NETWORKS.md](NETWORKS.md)

## [0.2.1] - 2026-02-09

### Fixed
- Restrict attachment download save paths to a safe download directory to prevent path traversal.
- Validate attachment download URLs against allowed hosts and attachment paths to prevent SSRF.
- Reject traversal characters in path parameters to avoid server-side path manipulation.
- Constrain file uploads from disk to a configured upload directory.
- Sanitize uploaded filenames to prevent path injection.
- Document HTTP error responses in OpenAPI metadata for endpoints.
- Fix async httpx event hooks to avoid NoneType await errors in logging.

## [0.2.0] - 2025-02-08

### Added
- ✅ **REST API server (FastAPI)**
  - HTTP interface for all MCP server functions
  - Interactive Swagger/OpenAPI docs
  - Endpoints for posts, comments, attachments, groups
  - File upload via multipart/form-data
  - Health check endpoint
  - Ready for production deployment

## [0.1.0] - 2025-02-08

### Added
- ✅ **Attachment uploads**
  - New `upload_attachment` tool for file uploads
  - `attachment_paths` parameter in `create_post` for auto upload
  - Image support (JPG, PNG, GIF, WebP)
  - Video support (MP4, WebM, MOV)
  - Document support (PDF)
  - Automatic MIME type detection

- ✅ **Attachment downloads**
  - `download_attachment` tool for file downloads
  - `get_post_attachments` tool for attachment listing
  - Download to file or as base64
  - URLs for different sizes (original, thumbnail, thumbnail2)

- ✅ **Groups**
  - `get_my_groups` - list user groups
  - `get_group_timeline` - get group posts
  - `get_group_info` - group info
  - `group_names` in `create_post` for posting to groups
  - Auto-resolve group names to feed IDs

- ✅ **Core MCP server functionality for FreeFeed API**
  - Read and write posts
  - Comments (create, edit, delete)
  - Timeline (home, posts, likes, comments, discussions)
  - Search with advanced operators
  - Users (profiles, subscriptions)
  - Likes and hide/unhide posts

### Technical details
- `httpx.AsyncClient` for async HTTP requests
- multipart/form-data for file uploads
- Automatic auth on client initialization
- Unit tests for all core functions
- Detailed docs with examples

### Not implemented
- Create/delete groups
- Manage group admins
- Ban users
- Update profile/avatar
- Reset password

## Future plans

### [0.2.0] - Planned
- Group management (create, configure, admin)
- Extended user profile management

### [0.3.0] - Planned
- Ban/unban users
- Notifications
- Data export
