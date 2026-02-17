# FreeFeed Images & Attachments

## Description

Use this skill to download and display images and other attachments from FreeFeed posts. This skill provides tools to fetch attachment files and show them inline when possible.

Available tools:
- `download_attachment` - Download attachments with flexible output options
- `get_attachment_image` - Optimized for displaying images inline
- `get_post_attachments` - Extract all attachment URLs from a post

## When to Use

**Always use this skill when:**
- User asks to "show images" or "display photos" from FreeFeed posts
- User says "покажи картинки" or "покажи фото"
- User requests to see attachments from a specific post
- User wants to view media content from FreeFeed timeline
- Displaying visual content from posts, comments, or user profiles

**Triggers:**
- "show the image/photo/picture"
- "display attachment"
- "let me see the image"
- "покажи изображение/фото/картинку"
- "что там на фото"
- Any request to view FreeFeed media content

## How to Use

### 1. Get Attachment URLs from Posts

First, retrieve post data using standard FreeFeed tools:

```python
# Get a specific post
post = get_post(post_id="...")

# Or get from timeline
timeline = get_timeline(timeline_type="home", limit=10)
```

### 2. Extract Attachment Information

Posts contain attachment metadata in the `attachments` array:

```python
# Each attachment has:
{
  "id": "attachment-uuid",
  "mediaType": "image",  # or "video", "audio", "general"
  "url": "https://media.freefeed.net/attachments/...",
  "imageSizes": {
    "t": {"url": "...", "width": 150, "height": 150},     # thumbnail
    "t2": {"url": "...", "width": 300, "height": 300},    # medium
    "o": {"url": "...", "width": 1024, "height": 768}     # original
  },
  "fileName": "photo.jpg",
  "fileSize": 245678
}
```

### 3. Download and Display Images

Use `get_attachment_image` for inline display:

```python
# Best for images - shows them directly to user
result = get_attachment_image(
    attachment_url="https://media.freefeed.net/attachments/abc123",
    max_bytes=2000000  # 2MB limit for inline display
)
```

Or use `download_attachment` for more control:

```python
# Download with options
result = download_attachment(
    attachment_url="https://media.freefeed.net/attachments/abc123",
    prefer_image=True,      # Return image content when possible
    max_bytes=2000000,      # Max size for inline
    save_path=None          # Optional: save to file instead
)
```

### 4. Handle Different Attachment Types

**Images (recommended approach):**
```python
# For images, always use get_attachment_image
image = get_attachment_image(
    attachment_url=attachment["url"]
)
# Claude will display the image inline to the user
```

**Large files or videos:**
```python
# For files >2MB or non-images
result = download_attachment(
    attachment_url=attachment["url"],
    prefer_image=False  # Just get URL
)
# Provide URL link to user
```

**Multiple attachments from a post:**
```python
# Extract all attachments first
attachments = get_post_attachments(post_id="abc123")

# Then download each one
for att in attachments["attachments"]:
    if att["mediaType"] == "image":
        get_attachment_image(attachment_url=att["url"])
```

## Image Size Selection

FreeFeed provides multiple image sizes. Choose appropriately:

- **Thumbnail (`t`)**: 150x150px - **USE FOR TIMELINE BROWSING** (default for feed)
- **Medium (`t2`)**: 300x300px - Use for inline gallery views or when user wants better quality
- **Original (`o`)**: Full resolution - Use when user explicitly requests full-size or needs details

**IMPORTANT: Always use thumbnail size when auto-displaying images in timeline/feed!**

Example:
```python
# Get thumbnail size for timeline (RECOMMENDED)
thumbnail_url = attachment["imageSizes"]["t"]["url"]
get_attachment_image(attachment_url=thumbnail_url)

# Get medium size for better quality when requested
medium_url = attachment["imageSizes"]["t2"]["url"]
get_attachment_image(attachment_url=medium_url)

# Get original only when user explicitly asks
original_url = attachment["imageSizes"]["o"]["url"]  # or just attachment["url"]
get_attachment_image(attachment_url=original_url)
```

## Best Practices

### DO:
✅ Use `get_attachment_image` for images by default
✅ Check file size before downloading large files
✅ Use appropriate image size (thumbnail/medium/original)
✅ Download multiple images sequentially, not in parallel
✅ Inform user when images are too large to display inline

### DON'T:
❌ Try to download images >2MB inline without warning user
❌ Use `download_attachment` when `get_attachment_image` is sufficient
❌ Download videos or large files without explicit user request
❌ Forget to handle cases where attachment URL might be invalid

## Common Patterns

### Pattern 1: Auto-display thumbnails when browsing timeline (DEFAULT BEHAVIOR)
**⚡ IMPORTANT: Always show image previews automatically when displaying timeline!**

When user asks to see their feed/timeline without specifically mentioning images, still show thumbnails:

```python
# Get recent timeline
timeline = get_timeline(timeline_type="home", limit=10)

# ALWAYS show thumbnail previews for posts with images
for post in timeline["posts"]:
    # Display post text/info first
    print(f"@{post['author']}: {post['body']}")

    # Then automatically show thumbnails for any images
    attachments_data = lookup_attachments_in_response(post["attachments"])
    for att in attachments_data:
        if att["mediaType"] == "image":
            # CRITICAL: Use thumbnail URL for timeline browsing (fast & small)
            # FreeFeed provides image sizes: t (150px), t2 (300px), o (original)
            # NOTE: imageSizes may not be present in timeline responses!

            image_url = None
            if "imageSizes" in att and att["imageSizes"]:
                # Prefer thumbnail if available
                if "t" in att["imageSizes"]:
                    image_url = att["imageSizes"]["t"].get("url")

            # Fallback to base URL if no imageSizes
            if not image_url:
                # Construct thumbnail URL from base attachment URL
                # Format: https://freefeed.net/attachments/{id} -> add /t for thumbnail
                base_url = att.get("url", f"https://freefeed.net/attachments/{att['id']}")
                # Try thumbnail endpoint first (smaller, faster)
                image_url = f"{base_url}/t"

            # Auto-display thumbnail - NO need to ask user
            try:
                get_attachment_image(attachment_url=image_url)
            except:
                # If thumbnail fails, try base URL as final fallback
                if "/t" in image_url:
                    get_attachment_image(attachment_url=att.get("url", base_url))
```

**Why this matters:**
- Users expect to see images when browsing social media
- "Show my feed" implicitly means "show posts AND their images"
- **Thumbnails (150px) are small and load MUCH faster than originals**
- Better user experience - visual context at a glance
- Saves bandwidth and improves performance
- **Handles both timeline responses (no imageSizes) and full post data (with imageSizes)**

### Pattern 2: Show full-size images from specific post
```python
# When user specifically asks about images in a post
post = get_post(post_id="...")

for att in post["attachments"]:
    if att["mediaType"] == "image":
        # Use original size when user explicitly requests images
        get_attachment_image(attachment_url=att["url"])
        print(f"📷 {att['fileName']} ({att['fileSize']} bytes)")
```

### Pattern 3: Show specific user's photos
```python
# Get user's posts
posts = get_timeline(
    timeline_type="posts",
    username="alice",
    limit=10
)

# Filter and show only images
for post in posts["posts"]:
    for att in post.get("attachments", []):
        if att["mediaType"] == "image":
            get_attachment_image(attachment_url=att["url"])
```

### Pattern 4: Download attachment to file
```python
# When user wants to save attachment
download_attachment(
    attachment_url="https://media.freefeed.net/attachments/...",
    save_path="/tmp/freefeed_image.jpg"
)
```

## Error Handling

Handle common errors gracefully:

```python
try:
    result = get_attachment_image(attachment_url=url)
    if not result:
        print("⚠️ Could not load image. URL may be invalid.")
except Exception as e:
    print(f"❌ Error downloading image: {e}")
    print("🔗 View in browser: " + url)
```

## Examples

### Example 1: Show image from post
```
User: покажи картинку из того поста про кино
Claude: [calls get_post for the cinema post]
        [extracts attachment URL]
        [calls get_attachment_image with URL]
        [displays image to user]
```

### Example 2: Gallery from user timeline
```
User: show me photos from @alice's recent posts
Claude: [calls get_timeline for alice's posts]
        [filters posts with images]
        [calls get_attachment_image for each]
        [displays images with post context]
```

### Example 3: Handle large file
```
User: покажи вложение из директа
Claude: [gets attachment URL]
        [checks file size: 5MB]
        [calls download_attachment with prefer_image=false]
        "This file is too large to display inline (5MB).
         You can view it here: [URL]"
```

## Technical Notes

- **Max inline size**: 2MB by default (configurable via `max_bytes`)
- **Supported formats**: Images (JPEG, PNG, GIF, WebP), Videos, PDFs, Documents
- **Image display**: Automatically rendered inline when <2MB
- **Fallback**: Always provides URL when inline display fails
- **Network**: Uses FreeFeed's CDN (media.freefeed.net)

## Integration with Other Tools

Combine with FreeFeed tools:
- `get_post` → `get_attachment_image` (show images from specific post)
- `get_timeline` → `get_post_attachments` → `get_attachment_image` (gallery view)
- `search_posts` → filter images → `get_attachment_image` (search images)

## Troubleshooting

**Problem**: Image won't display
- Check if URL is valid (starts with https://media.freefeed.net)
- Verify file size is <2MB
- Try using smaller image size (t2 instead of o)

**Problem**: Slow loading
- Use thumbnail or medium sizes instead of original
- Reduce max_bytes limit
- Download sequentially, not in parallel

**Problem**: Wrong image shown
- Double-check post_id and attachment index
- Verify you're using correct attachment URL from metadata
