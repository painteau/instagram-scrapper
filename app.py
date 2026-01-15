import os
import sys
import logging
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

def scrape_post(shortcode):
    post = Post.from_shortcode(L.context, shortcode)
    L.download_post(post, target=shortcode)

    logger.info(f"Downloaded post for: {shortcode}")

    return jsonify({
        "shortcode": shortcode,
        "video": f"/data/instaloader/{shortcode}/{shortcode}.mp4",
        "description": post.caption or ""
    })


def extract_shortcode(url):
    parsed = urlparse(url)
    path = parsed.path or ""
    segments = [segment for segment in path.split("/") if segment]
    if len(segments) >= 2 and segments[0] in ("reel", "p"):
        return segments[1]
    raise ValueError("Invalid URL format")

@app.route("/scrape", methods=["POST"])
def scrape():
    logger.info("Starting Instaloader Job")
    
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
