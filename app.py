import os
import sys
import time
import shutil
import logging
from collections import deque
from urllib.parse import urlparse
from flask import Flask, request, jsonify
from instaloader import Instaloader, Post
from instaloader.exceptions import (
    InstaloaderException,
    QueryReturnedNotFoundException,
    QueryReturnedForbiddenException,
    PrivateProfileNotFollowedException,
    LoginRequiredException,
    TooManyRequestsException,
    ConnectionException,
)

API_KEY = os.getenv("API_KEY") or ""
MAX_URL_LENGTH = int(os.getenv("MAX_URL_LENGTH", "512"))
ALLOWED_URL_SCHEMES = ("https",)
ALLOWED_URL_HOSTS = ("www.instagram.com", "instagram.com")
MAX_JSON_BODY_BYTES = int(os.getenv("MAX_JSON_BODY_BYTES", "4096"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "30"))
MAX_MEDIA_AGE_DAYS = int(os.getenv("MAX_MEDIA_AGE_DAYS", "7"))
MEDIA_CLEANUP_INTERVAL_SECONDS = int(os.getenv("MEDIA_CLEANUP_INTERVAL_SECONDS", "3600"))

rate_limit_store = {}
last_media_cleanup = 0.0


def check_api_key():
    if not API_KEY:
        return None
    header_key = request.headers.get("X-API-Key")
    if header_key != API_KEY:
        logger.warning("Unauthorized request: invalid or missing API key")
        return jsonify({"error": "Unauthorized"}), 401
    return None

logger = logging.getLogger(__name__)
app = Flask(__name__)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
    force=True
)

L = Instaloader(
        dirname_pattern="/data/instaloader/{shortcode}", 
        filename_pattern="{shortcode}", 
        download_comments=False)


def get_client_ip():
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr or "unknown"


def check_rate_limit(ip):
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS
    bucket = rate_limit_store.get(ip)
    if bucket is None:
        bucket = deque()
        rate_limit_store[ip] = bucket
    while bucket and bucket[0] < window_start:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT_MAX_REQUESTS:
        return True
    bucket.append(now)
    return False


def cleanup_old_media(now=None):
    root = "/data/instaloader"
    if not os.path.isdir(root):
        return
    if now is None:
        now = time.time()
    cutoff = now - MAX_MEDIA_AGE_DAYS * 86400
    try:
        entries = os.listdir(root)
    except OSError as e:
        logger.error(f"Failed to list media directory {root}: {e}")
        return
    for name in entries:
        path = os.path.join(root, name)
        try:
            stat = os.stat(path)
        except OSError:
            continue
        if stat.st_mtime < cutoff:
            try:
                shutil.rmtree(path)
                logger.info(f"Removed old media directory: {path}")
            except Exception as e:
                logger.error(f"Failed to remove old media directory {path}: {e}")

def scrape_post(shortcode):
    post = Post.from_shortcode(L.context, shortcode)
    L.download_post(post, target=shortcode)

    logger.info(f"Downloaded post for: {shortcode}")

    global last_media_cleanup
    now = time.time()
    if now - last_media_cleanup > MEDIA_CLEANUP_INTERVAL_SECONDS:
        cleanup_old_media(now=now)
        last_media_cleanup = now

    return jsonify({
        "shortcode": shortcode,
        "video": f"/data/instaloader/{shortcode}/{shortcode}.mp4",
        "description": post.caption or "",
        "cdn_url": post.video_url if post.is_video else post.url
    })


def extract_shortcode(url):
    if len(url) > MAX_URL_LENGTH:
        raise ValueError("Invalid URL format")
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_URL_SCHEMES:
        raise ValueError("Invalid URL format")
    host = parsed.netloc.lower()
    if host not in ALLOWED_URL_HOSTS:
        raise ValueError("Invalid URL format")
    path = parsed.path or ""
    segments = [segment for segment in path.split("/") if segment]
    if len(segments) >= 2 and segments[0] in ("reel", "p"):
        return segments[1]
    raise ValueError("Invalid URL format")

@app.route("/scrape", methods=["POST"])
def scrape():
    logger.info("Starting Instaloader Job")
    ip = get_client_ip()

    content_length = request.content_length
    if content_length is not None and content_length > MAX_JSON_BODY_BYTES:
        logger.warning(f"Request body too large from IP {ip}: {content_length} bytes")
        return jsonify({"error": "Request body too large"}), 413

    if check_rate_limit(ip):
        logger.warning(f"Rate limit exceeded for IP {ip}")
        return jsonify({"error": "Too many requests"}), 429

    auth_error = check_api_key()
    if auth_error is not None:
        return auth_error

    data = request.get_json()
    url = data.get("url")
    if not url:
        logger.warning("Missing 'url' in request.")
        return jsonify({"error": "Missing 'url'"}), 400

    try:
        shortcode = extract_shortcode(url)
    except ValueError:
        logger.info(f"Error: Could not extract shortcode from URL '{url}'")
        return jsonify({"error": "Invalid URL format"}), 400
    
    logger.info(f"Scraping Instagram post with shortcode: {shortcode}")
    try:
        return scrape_post(shortcode)
    except QueryReturnedNotFoundException as e:
        logger.warning(f"Post not found for shortcode {shortcode}: {e}")
        return jsonify({"error": "Post not found"}), 404
    except (QueryReturnedForbiddenException, PrivateProfileNotFollowedException, LoginRequiredException) as e:
        logger.warning(f"Access denied for shortcode {shortcode}: {e}")
        return jsonify({"error": "Access to this post is forbidden or requires login"}), 403
    except TooManyRequestsException as e:
        logger.warning(f"Rate limit reached while scraping {shortcode}: {e}")
        return jsonify({"error": "Rate limit reached when contacting Instagram"}), 429
    except ConnectionException as e:
        message = str(e)
        if "Please wait a few minutes before you try again" in message:
            logger.warning(f"Rate limit (Please wait) while scraping {shortcode}: {e}")
            return jsonify({"error": "Rate limit reached when contacting Instagram"}), 429
        logger.error(f"Connection error while scraping post {shortcode}: {e}")
        return jsonify({"error": "Unable to reach Instagram"}), 503
    except InstaloaderException as e:
        logger.error(f"Instaloader error while scraping post {shortcode}: {e}")
        return jsonify({"error": "Unexpected error while contacting Instagram"}), 502
    except Exception as e:
        logger.error(f"Error scraping post {shortcode}: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/health", methods=["GET"])
def health():
    logger.debug("Health check called.")
    return "OK", 200

if __name__ == "__main__":
    logger.info("Starting Instaloader Flask app...")
    app.run(host="0.0.0.0", port=5633)
