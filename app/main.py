"""
Cloud Functions (2nd gen) entry point.

Cloud Functions Python runtime uses the Functions Framework, which can serve
a WSGI app directly. We just expose the Flask app as a function-shaped
callable. Deploy with:

    gcloud functions deploy boutique \
        --gen2 --runtime=python312 --region=us-central1 \
        --source=. --entry-point=boutique \
        --trigger-http --allow-unauthenticated \
        --set-env-vars GCS_BUCKET=$GCS_BUCKET

The function name 'boutique' below must match --entry-point above.
"""

import functions_framework

from app import app as flask_app


@functions_framework.http
def boutique(request):
    # Hand the incoming request to the Flask WSGI app and return its response.
    # This lets us reuse the exact same routes/templates as the VM and
    # container deployments — no code duplication.
    with flask_app.request_context(request.environ):
        return flask_app.full_dispatch_request()
