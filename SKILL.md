---
name: freefeed-attachments
description: Downloading and displaying FreeFeed attachments in MCP, including inline image content with URL fallback. Use this when users ask to view post attachments or render images from FreeFeed.
license: Complete terms in LICENSE
---

This skill defines MCP tools for fetching FreeFeed attachments and returning image content when possible. The goal is to display images inline for MCP clients that support `image` content, while always providing a URL fallback.

This happens in two steps:
1. Resolve a usable attachment URL (including preview URLs when the base URL returns HTML).
2. Return `image` content if the response is an image and within size limits, otherwise return a URL-only response.

## download_attachment

Download an attachment and optionally save it to disk. If the attachment is an image and small enough, returns `image` content plus a text fallback.

Usage:
- attachment_url: Full attachment URL from post metadata
- save_path: Optional path to save locally
- prefer_image: Return image content when possible (default: true)
- max_bytes: Maximum bytes allowed for inline image data (default: 2000000)

Behavior:
- If the file is an image and within `max_bytes`, returns `image` content plus a text fallback with URL
- If the file is too large, returns a URL fallback only
- If `save_path` is provided, saves to file and returns the saved path

Example:
```json
{
  "name": "download_attachment",
  "arguments": {
    "attachment_url": "https://freefeed.net/attachments/ATTACHMENT_ID",
    "prefer_image": true,
    "max_bytes": 2000000
  }
}
```

## get_attachment_image

Download an attachment and return image content when possible. If the server returns HTML, resolves a preview URL before downloading.

Usage:
- attachment_url: Full attachment URL from post metadata
- max_bytes: Maximum bytes allowed for inline image data (default: 2000000)

Behavior:
- Returns `image` content plus a text fallback with URL
- If the file is too large, returns a URL fallback only
- If the attachment is not an image, returns a text response with an error and URL

Example:
```json
{
  "name": "get_attachment_image",
  "arguments": {
    "attachment_url": "https://freefeed.net/attachments/ATTACHMENT_ID",
    "max_bytes": 2000000
  }
}
```

## Troubleshooting

- HTML instead of image: The base URL may return a landing page. The tool will resolve a preview URL and retry automatically.
- 404 Not Found: The attachment URL might be a media variant. The tool tries fallback URLs based on the attachment id.
- Too large to inline: Increase `max_bytes` or use `download_attachment` with `save_path` to save locally.
