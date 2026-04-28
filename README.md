# 📸 instagram-scrapper

Minimal HTTP service to download Instagram posts (Reels or regular posts) via a JSON API, built with Flask and Instaloader and packaged as a Docker container.

This Docker image is compatible with the following architectures:
- `linux/amd64` (x86_64)
- `linux/arm64` (Apple Silicon, Raspberry Pi 4/5)
- `linux/arm/v7` (Raspberry Pi 3, etc.)

## ✨ Features

- `/scrape` endpoint to download an Instagram post from its URL.
- Automatic extraction of the post *shortcode* from the URL.
- Media download handled by `instaloader`.
- JSON response containing:
  - the `shortcode`,
  - the post description (caption),
  - the `cdn_url` (direct link to the video/image on Instagram's CDN),
  - the `original_url` (the URL that was sent to the API).
- `/health` endpoint to check the service status.

## 🔌 API

### `POST /scrape`

If no API key environment variable is defined, this endpoint is publicly accessible.  
If the `API_KEY` environment variable is set, a key must be provided in the HTTP header `X-API-Key`.

Request body (JSON):

```json
{
  "url": "https://www.instagram.com/reel/SHORTCODE/"
}
```

Successful response (`200 OK`):

```json
{
  "shortcode": "SHORTCODE",
  "description": "Post caption or empty string",
  "cdn_url": "https://scontent-...",
  "original_url": "https://www.instagram.com/reel/SHORTCODE/"
}
```

Example `curl` call (with API key enabled):

```bash
# API_KEY should be provided securely by your environment or secret manager.
curl -X POST http://localhost:5633/scrape \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "url": "https://www.instagram.com/reel/SHORTCODE/"
  }'
```

Main status codes:

- `200 OK`: download succeeded.
- `400 Bad Request`:
  - missing `url` field,
  - invalid URL format (shortcode cannot be extracted).
- `403 Forbidden`: access forbidden or login required for the post.
- `404 Not Found`: post does not exist or has been removed.
- `429 Too Many Requests`: Instagram rate limit reached.
- `500 Internal Server Error`: unexpected internal error.
- `502 Bad Gateway`: unexpected error while contacting Instagram via Instaloader.
- `503 Service Unavailable`: Instagram could not be reached.

### `GET /download/<shortcode>`

Download the media file previously scraped for a given shortcode.

Requires `X-API-Key` header if `API_KEY` is set.

- Returns the file as an attachment (`.mp4`, `.jpg`, or `.png`).
- `400` if the shortcode is invalid.
- `404` if no media exists for that shortcode.

Example:

```bash
curl -OJ -H "X-API-Key: $API_KEY" http://localhost:5633/download/SHORTCODE
```

### `GET /health`

Used to check that the application is running.

Example `curl` call:

```bash
curl http://localhost:5633/health
```

- Response body: `OK`
- Status code: `200`

## 🔗 Instagram URL handling

The shortcode is extracted from the URL path. Supported formats include, for example:

- `https://www.instagram.com/reel/SHORTCODE/`
- `https://www.instagram.com/reel/SHORTCODE`
- `https://www.instagram.com/reel/SHORTCODE/?utm_source=...`
- `https://www.instagram.com/p/SHORTCODE/`

Other variants can be supported as long as the path follows the general pattern `/<reel|p>/<shortcode>[...]`.

Additional safety checks are applied to the input URL:

- only `https` URLs are accepted,
- the host must be `instagram.com` or `www.instagram.com`,
- the URL length is limited (default: 512 characters).

Any URL that does not pass these checks is rejected with a `400 Bad Request` and `"Invalid URL format"`.

## ⚠️ Error handling and rate limiting

Errors raised by Instaloader (private posts, removed content, rate limiting, network issues, etc.) are mapped to HTTP status codes where possible:

- not found → `404 Not Found`,
- forbidden / private / login required → `403 Forbidden`,
- rate limit reached or "Please wait a few minutes before you try again" → `429 Too Many Requests`,
- network / connection issues → `503 Service Unavailable`,
- other Instaloader errors → `502 Bad Gateway`,
- unexpected errors in the app → `500 Internal Server Error`.

The JSON error payload follows the structure:

```json
{
  "error": "Human-readable error message"
}
```

## 📦 Request limits, rate limiting, and file storage

- Maximum JSON body size:
  - Requests larger than `MAX_JSON_BODY_BYTES` (default: 4096 bytes) are rejected with `413 Payload Too Large`.
- Per-IP rate limiting:
  - By default, a simple in-memory rate limiter limits each IP to `RATE_LIMIT_MAX_REQUESTS` requests per `RATE_LIMIT_WINDOW_SECONDS` (defaults: 30 requests per 60 seconds).
  - Exceeding the limit returns `429 Too Many Requests`.
  - The store is capped at `RATE_LIMIT_MAX_IPS` entries (default: 10 000) — oldest IPs are evicted when the cap is reached.

Downloaded files are stored inside the container under:

- `/data/instaloader/{shortcode}/{shortcode}.mp4`

The `/data` path is meant to be mounted as a volume when running the application in Docker, so that media files are persisted on the host.

Old media is automatically cleaned up:

- directories under `/data/instaloader` older than `MAX_MEDIA_AGE_DAYS` (default: 7 days) are removed periodically when new downloads occur.

Local run example:

```bash
docker build -t instagram-scrapper .

docker run --rm \
  -p 5633:5633 \
  -v $(pwd)/data:/data \
  instagram-scrapper
```

Downloaded files will then be available on your machine under `./data/instaloader`.

## 🚀 Deployment and CI/CD

- Dockerfile based on `ghcr.io/painteau/python-ffmpeg-flask-gunicorn:latest`, with `ffmpeg`, `flask` and `gunicorn` pre-installed (only `instaloader` is added on top).
- Application served by `gunicorn` on port `5633` with a 60 second request timeout.
- GitHub Actions workflow builds and publishes a multi-architecture Docker image (`linux/amd64`, `linux/arm64`, `linux/arm/v7`) to GitHub Container Registry and signs the image with `cosign`.

## ⚙️ Configuration via environment variables

Some behaviors can be tuned via environment variables:

- `API_KEY`:
  - If unset or empty: `/scrape` is open (no auth).
  - If set: `/scrape` requires `X-API-Key` header matching this value.
- `MAX_URL_LENGTH` (default: `512`):
  - Maximum length of the input URL.
- `MAX_JSON_BODY_BYTES` (default: `4096`):
  - Maximum size of the JSON request body.
- `RATE_LIMIT_WINDOW_SECONDS` (default: `60`):
  - Rate limiting window duration, in seconds.
- `RATE_LIMIT_MAX_REQUESTS` (default: `30`):
  - Maximum number of requests per IP in each rate limiting window.
- `RATE_LIMIT_MAX_IPS` (default: `10000`):
  - Maximum number of IPs tracked in memory; oldest entry evicted when reached.
- `TRUST_PROXY` (default: unset):
  - Set to `1` or `true` to read the real client IP from `X-Forwarded-For`. Enable only when behind a trusted reverse proxy.
- `MAX_MEDIA_AGE_DAYS` (default: `7`):
  - Maximum age (in days) for media directories under `/data/instaloader`.
- `MEDIA_CLEANUP_INTERVAL_SECONDS` (default: `3600`):
  - Minimum interval between automatic cleanup runs.

🔒 **Security recommendations for secrets**

- Do not commit `API_KEY` or other secrets to the repository.
- Prefer secret management mechanisms (Docker/Kubernetes secrets, GitHub Actions secrets, cloud secret managers) over plain `.env` files.
- Avoid passing secrets directly on the command line (they may end up in shell history); instead:
  - export them in your environment (`export API_KEY=...`) or
  - inject them via your orchestrator's secret mechanism.

## 📄 License

This project is distributed under the MIT License. See the `LICENSE` file for details.

