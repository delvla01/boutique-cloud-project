"""
Online Boutique – simplified Flask version with cart + checkout.

Single-process Flask app that serves a product grid, product detail pages,
a shopping cart, and a checkout flow. Product metadata lives in
products.json. Images are served from a public Google Cloud Storage bucket
whose name is read from the GCS_BUCKET env var.

The same file runs in all three deployment modes:
  - VM (Compute Engine):  gunicorn  (started by systemd / startup script)
  - Container (Cloud Run): gunicorn via the Dockerfile
  - Serverless (Cloud Functions): imported by main.py via Functions Framework

Cart state lives in Flask's session (signed cookie). It's per-user and
survives across page loads, but is lost if the instance restarts. That's
a reasonable tradeoff for a demo — a real e-commerce app would back the
cart with Redis or a database.
"""

import json
import os
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request, session, url_for

app = Flask(__name__)

# Sign session cookies. In production this would be set via Secret Manager
# and never committed; for this demo we read it from env and fall back to
# a dev-only default so local runs Just Work without setup.
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

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


# ---------- cart helpers ----------------------------------------------------

def get_cart():
    """Return the cart dict from session, creating it if absent.

    Shape: { product_id: quantity, ... }. We keep it small and JSON-friendly
    so it serializes into the session cookie cleanly.
    """
    if "cart" not in session:
        session["cart"] = {}
    return session["cart"]


def cart_summary():
    """Expand the cart dict into a list of line items with subtotals, plus
    the grand total. Used by the cart and checkout pages."""
    cart = get_cart()
    items = []
    total = 0.0
    for product_id, qty in cart.items():
        product = PRODUCTS_BY_ID.get(product_id)
        if not product:
            # Product was removed from catalog since it was added to cart.
            # Skip it rather than crash; a real app would notify the user.
            continue
        subtotal = product["priceUsd"] * qty
        total += subtotal
        items.append({
            "product": product,
            "quantity": qty,
            "subtotal": subtotal,
        })
    return items, total


def cart_item_count():
    """Total number of items across all products. For the header badge."""
    return sum(get_cart().values())


@app.context_processor
def inject_globals():
    """Make cart count and image base available to every template without
    threading them through each render_template() call."""
    return {
        "image_base": IMAGE_BASE_URL,
        "cart_count": cart_item_count(),
    }


# ---------- routes ----------------------------------------------------------

@app.route("/")
def home():
    return render_template("home.html", products=PRODUCTS)


@app.route("/product/<product_id>")
def product(product_id):
    item = PRODUCTS_BY_ID.get(product_id)
    if item is None:
        abort(404)
    return render_template("product.html", product=item)


@app.route("/cart/add/<product_id>", methods=["POST"])
def add_to_cart(product_id):
    if product_id not in PRODUCTS_BY_ID:
        abort(404)
    cart = get_cart()
    # Default qty=1, but accept any positive integer from the form so we
    # could later expose a quantity selector on the product page.
    qty = max(1, int(request.form.get("quantity", 1)))
    cart[product_id] = cart.get(product_id, 0) + qty
    session.modified = True  # mutating nested dict requires explicit flag
    return redirect(url_for("view_cart"))


@app.route("/cart/remove/<product_id>", methods=["POST"])
def remove_from_cart(product_id):
    cart = get_cart()
    cart.pop(product_id, None)
    session.modified = True
    return redirect(url_for("view_cart"))


@app.route("/cart")
def view_cart():
    items, total = cart_summary()
    return render_template("cart.html", items=items, total=total)


@app.route("/checkout")
def checkout():
    items, total = cart_summary()
    if not items:
        # Don't let users land on an empty checkout page; bounce them to
        # the cart which shows an empty-state message.
        return redirect(url_for("view_cart"))
    return render_template("checkout.html", items=items, total=total)


@app.route("/checkout/complete", methods=["POST"])
def checkout_complete():
    """Simulated order placement. No payment, no persistence — just
    capture the totals, clear the cart, and show a confirmation page.
    A real app would write an order row to a database here."""
    items, total = cart_summary()
    if not items:
        return redirect(url_for("home"))

    # Generate a fake order id from the session for visual interest.
    # In production this would be a row id from the orders table.
    import hashlib, time
    order_id = "ORD-" + hashlib.md5(
        f"{session.get('_id', '')}{time.time()}".encode()
    ).hexdigest()[:8].upper()

    item_count = sum(i["quantity"] for i in items)

    # Clear the cart now that the "order" is "placed".
    session["cart"] = {}
    session.modified = True

    return render_template(
        "order_complete.html",
        order_id=order_id,
        item_count=item_count,
        total=total,
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
