# instagram-scrapper

Minimal HTTP service to download Instagram posts (Reels or regular posts) via a JSON API, built with Flask and Instaloader and packaged as a Docker container.

## Features

- `/scrape` endpoint to download an Instagram post from its URL.
- Automatic extraction of the post *shortcode* from the URL.
- Media download handled by `instaloader`.
- JSON response containing:
  - the `shortcode`,
  - the path to the downloaded video file,
  - the post description (caption).
- `/health` endpoint to check the service status.

## API

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
  "video": "/data/instaloader/SHORTCODE/SHORTCODE.mp4",
  "description": "Post caption or empty string"
}
```

Example `curl` call (with API key enabled):

```bash
curl -X POST http://localhost:5633/scrape \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
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

### `GET /health`

Used to check that the application is running.

Example `curl` call:

```bash
curl http://localhost:5633/health
```

- Response body: `OK`
- Status code: `200`

## Instagram URL handling

The shortcode is extracted from the URL path. Supported formats include, for example:

- `https://www.instagram.com/reel/SHORTCODE/`
- `https://www.instagram.com/reel/SHORTCODE`
- `https://www.instagram.com/reel/SHORTCODE/?utm_source=...`
- `https://www.instagram.com/p/SHORTCODE/`

Other variants can be supported as long as the path follows the general pattern `/<reel|p>/<shortcode>[...]`.

## Error handling with Instaloader

Errors raised by Instaloader (private posts, removed content, rate limiting, network issues, etc.) are mapped to HTTP status codes where possible:

- not found → `404 Not Found`,
- forbidden / private / login required → `403 Forbidden`,
- rate limit reached → `429 Too Many Requests`,
- network / connection issues → `503 Service Unavailable`,
- other Instaloader errors → `502 Bad Gateway`,
- unexpected errors in the app → `500 Internal Server Error`.

The JSON error payload follows the structure:

```json
{
  "error": "Human-readable error message"
}
```

## File storage and `/data` volume

Downloaded files are stored inside the container under:

- `/data/instaloader/{shortcode}/{shortcode}.mp4`

The `/data` path is meant to be mounted as a volume when running the application in Docker, so that media files are persisted on the host.

Local run example:

```bash
docker build -t instagram-scrapper .

docker run --rm \
  -p 5633:5633 \
  -v $(pwd)/data:/data \
  instagram-scrapper
```

Downloaded files will then be available on your machine under `./data/instaloader`.

> Note: for now, the download path is fixed to `/data/instaloader`. A possible improvement would be to make this path configurable via an environment variable.

## Deployment and CI/CD

- Dockerfile based on `python:3.14-slim`, with minimal dependencies installed (`instaloader`, `flask`, `gunicorn`, `ffmpeg`).
- Application served by `gunicorn` on port `5633`.
- GitHub Actions workflow builds and publishes a multi-architecture Docker image (`linux/amd64`, `linux/arm64`) to GitHub Container Registry and signs the image with `cosign`.

## License

This project is distributed under the MIT License. See the `LICENSE` file for details.

