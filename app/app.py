"""
Online Boutique – simplified Flask version.

Single-process Flask app that serves a product grid and product detail pages.
Product metadata lives in products.json. Images are served from a public
Google Cloud Storage bucket whose name is read from the GCS_BUCKET env var.

The same file runs in all three deployment modes:
  - VM (Compute Engine):  python app.py  (or gunicorn)
  - Container (Cloud Run): gunicorn via the Dockerfile
  - Serverless (Cloud Functions): imported by main.py via Functions Framework
"""

import json
import os
from pathlib import Path

from flask import Flask, abort, render_template

app = Flask(__name__)

# Where product images are hosted. In all three deploys this points to the
# same public GCS bucket, which is how we satisfy the "store images in cloud
# storage" requirement uniformly across deployment modes.
GCS_BUCKET = os.environ.get("GCS_BUCKET", "")
IMAGE_BASE_URL = (
    f"https://storage.googleapis.com/{GCS_BUCKET}" if GCS_BUCKET else "/static/img"
)

# Load product catalog once at startup. Small enough to keep in memory.
PRODUCTS_FILE = Path(__file__).parent / "products.json"
with PRODUCTS_FILE.open() as f:
    PRODUCTS = json.load(f)["products"]
PRODUCTS_BY_ID = {p["id"]: p for p in PRODUCTS}


@app.route("/")
def home():
    return render_template(
        "home.html",
        products=PRODUCTS,
        image_base=IMAGE_BASE_URL,
    )


@app.route("/product/<product_id>")
def product(product_id):
    item = PRODUCTS_BY_ID.get(product_id)
    if item is None:
        abort(404)
    return render_template(
        "product.html",
        product=item,
        image_base=IMAGE_BASE_URL,
    )


@app.route("/healthz")
def healthz():
    # Used by the VM load balancer health check and handy for sanity-testing
    # the container and function deploys too.
    return {"status": "ok", "bucket": GCS_BUCKET or "local"}, 200


@app.errorhandler(404)
def not_found(_):
    return render_template("404.html"), 404


if __name__ == "__main__":
    # Local / VM entry point. Cloud Run uses gunicorn (see Dockerfile);
    # Cloud Functions uses the Functions Framework (see main.py).
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
