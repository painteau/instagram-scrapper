# CLAUDE GUIDE

This file explains how to quickly understand and work with this repository.

## 1. What this project does

- Minimal Flask HTTP service that downloads Instagram posts (Reels or regular posts) using `instaloader`.
- Main responsibilities:
  - Accept a POST `/scrape` with a JSON body containing an Instagram URL.
  - Extract the shortcode from the URL.
  - Use Instaloader to download the media.
  - Return JSON with the shortcode, video path, caption, and a CDN URL.
  - Provide a simple healthcheck at `GET /health`.

## 2. Where the important code lives

- Application entrypoint: [app.py](./app.py)
  - Creates the Flask app and configures logging.
  - Configures `Instaloader` with:
    - `dirname_pattern="/data/instaloader/{shortcode}"`
    - `filename_pattern="{shortcode}"`
  - `scrape_post(shortcode)`:
    - Builds a `Post` from the shortcode.
    - Downloads the post into `/data/instaloader/{shortcode}`.
    - Returns a JSON payload describing the downloaded media, including:
      - `shortcode`
      - `video` (path under `/data/instaloader`)
      - `description` (caption)
      - `cdn_url` (direct link to video/image on Instagram's CDN; temporary).
  - `extract_shortcode(url)`:
    - Uses `urllib.parse` to parse the URL.
    - Enforces security constraints on the URL:
      - `https` scheme only.
      - Host must be `instagram.com` or `www.instagram.com`.
      - URL length limited by `MAX_URL_LENGTH` (default 512).
    - Accepts paths like `/reel/<shortcode>` and `/p/<shortcode>`, with or without trailing slash and query params.
  - `check_api_key()`:
    - If `API_KEY` env var is not set, auth is disabled.
    - If `API_KEY` is set, requires header `X-API-Key` matching it, otherwise returns 401.
  - `/scrape` route:
    - Optionally enforces API key auth.
    - Validates request body and URL format.
    - Enforces:
      - Maximum JSON body size (`MAX_JSON_BODY_BYTES`, default 4096 bytes).
      - Per-IP in-memory rate limiting using `RATE_LIMIT_MAX_REQUESTS` and `RATE_LIMIT_WINDOW_SECONDS`.
    - Calls `scrape_post`.
    - Maps Instaloader exceptions to meaningful HTTP status codes (404, 403, 429, 503, 502, 500), including special handling for Instagram's "Please wait a few minutes" message as a 429.
  - `/health` route:
    - Returns `"OK"` with HTTP 200.

## 3. How error handling is structured

- Uses specific Instaloader exceptions (e.g. `QueryReturnedNotFoundException`, `QueryReturnedForbiddenException`, `TooManyRequestsException`, `ConnectionException`) and maps them to HTTP status codes:
  - 404 for missing posts.
  - 403 for private/forbidden/login-required posts.
  - 429 for rate limiting.
  - 503 for connection issues.
  - 502 for unexpected Instaloader failures.
  - 500 for generic internal errors.
- This mapping is important to preserve when modifying behavior; clients may rely on these codes.

## 4. Configuration and environment

- Docker:
  - See [Dockerfile](./Dockerfile) for the runtime environment.
  - Uses `ghcr.io/painteau/python-ffmpeg-flask-gunicorn:latest` as base image.
  - Base image already contains `ffmpeg`, `flask`, and `gunicorn`; Dockerfile only installs `instaloader`.
  - Runs the app via Gunicorn on `0.0.0.0:5633` using `app:app` with a 60 second timeout.
- Environment variables:
  - `API_KEY` (optional):
    - If unset or empty: `/scrape` is open (no auth).
    - If set: `/scrape` requires `X-API-Key` header matching this value.
  - `MAX_URL_LENGTH` (default: `512`):
    - Maximum allowed length for the input URL.
  - `MAX_JSON_BODY_BYTES` (default: `4096`):
    - Maximum allowed size (in bytes) for the JSON request body.
  - `RATE_LIMIT_WINDOW_SECONDS` (default: `60`):
    - Size of the rate limiting window.
  - `RATE_LIMIT_MAX_REQUESTS` (default: `30`):
    - Maximum number of requests per IP in each rate limiting window.
  - `MAX_MEDIA_AGE_DAYS` (default: `7`):
    - Maximum age for media directories under `/data/instaloader` before they are removed.
  - `MEDIA_CLEANUP_INTERVAL_SECONDS` (default: `3600`):
    - Minimum interval between automatic media cleanup runs.
- Storage:
  - Media is written under `/data/instaloader/{shortcode}/{shortcode}.mp4`.
  - When running in Docker, `/data` is intended to be a mounted volume from the host.

**Security notes for environment variables and secrets**

- `API_KEY` and other sensitive environment variables must never be committed to the repository.
- Do not print or log secret values; existing logging already avoids logging `API_KEY` and should remain that way.
- In production, rely on secret management provided by the platform:
  - Docker/Kubernetes secrets,
  - GitHub Actions/CI secrets,
  - Cloud secret managers.
- When giving examples, prefer using `$API_KEY` (coming from the environment) rather than hardcoding values.

## 5. How to run and test it quickly

- Local run with Docker (host will see downloaded data in `./data`):

```bash
docker build -t instagram-scrapper .

docker run --rm \
  -p 5633:5633 \
  -v $(pwd)/data:/data \
  instagram-scrapper
```

- With API key enabled:

```bash
docker run --rm \
  -p 5633:5633 \
  -v $(pwd)/data:/data \
  -e API_KEY=supersecret \
  instagram-scrapper
```

- Example requests:

```bash
curl -X POST http://localhost:5633/scrape \
  -H "Content-Type: application/json" \
  -H "X-API-Key: supersecret" \
  -d '{
    "url": "https://www.instagram.com/reel/SHORTCODE/"
  }'

curl http://localhost:5633/health
```

## 6. Files you should read first

To build a mental model of the project:

1. [README.md](./README.md) — high-level description of the API and behavior.
2. [app.py](./app.py) — actual implementation of routes, URL parsing, error handling.
3. [Dockerfile](./Dockerfile) — runtime environment and how the service is deployed.
4. [CHANGELOG.md](./CHANGELOG.md) — overview of what changed between versions.

## 7. Guidelines for future changes

- Keep the public API stable where possible:
  - Routes: `/scrape`, `/health`.
  - Request/response JSON shape.
  - Error codes for common failure cases.
- Preserve security expectations:
  - Honor `API_KEY` when set.
  - Do not log secrets or sensitive tokens.
- Keep the code simple and small:
  - This service is intentionally minimal; avoid unnecessary abstractions.
  - Use existing patterns in `app.py` when adding new behavior.
