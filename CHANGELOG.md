# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to Semantic Versioning.

## [0.2.0] - 2026-01-15

### Added

- Detailed README describing the API, supported URLs and `/data` volume.
- Example `curl` calls for `/scrape` and `/health` endpoints.
- MIT license file.
- Optional API key authentication via the `API_KEY` environment variable.
- Multi-architecture Docker support: `linux/amd64`, `linux/arm64`, and `linux/arm/v7`.
- `cdn_url` field in the `/scrape` response exposing the direct media URL on Instagram's CDN.
- Basic security controls:
  - URL validation (HTTPS only, `instagram.com` host, maximum URL length).
  - Request body size limit for JSON payloads.
  - Simple per-IP in-memory rate limiting on `/scrape`.
  - Automatic cleanup of old media under `/data/instaloader`.

### Changed

- Base Docker image updated to `ghcr.io/painteau/python-ffmpeg-flask-gunicorn:latest` (optimized with pre-installed ffmpeg/flask/gunicorn).
- Shortcode extraction improved to support more Instagram URL formats.
- Error handling with Instaloader refined with appropriate HTTP status codes (404, 403, 429, 503, 502).

## [0.1.0] - 2024-09-02

### Added

- Initial Flask service to download an Instagram post via the `/scrape` endpoint.
- `/health` endpoint for basic health checks.
- Initial Dockerfile based on `python:3.11-slim`.
