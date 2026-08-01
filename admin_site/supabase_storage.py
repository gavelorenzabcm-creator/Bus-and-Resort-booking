import os
import requests
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "uploads")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is missing from .env"
    )

# Still used for get_public_url() (no network call, just builds a URL string)
# and delete_file(). Upload is handled manually below via direct HTTP/1.1
# requests instead, since the SDK's storage client (storage3 -> httpx) uses
# HTTP/2 by default and has known issues where uploads stall indefinitely
# waiting on HTTP/2 flow control in some network environments (e.g. Vercel
# serverless -> Supabase Storage). Plain requests uses HTTP/1.1, sidestepping
# that entire class of bug.
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def upload_file(file_storage, filename):
    """Upload a file to Supabase Storage via a direct HTTP/1.1 request.

    Bypasses the Supabase SDK's storage client (storage3/httpx), which
    defaults to HTTP/2 and has been observed to hang indefinitely on some
    networks (serverless -> Supabase Storage), causing "read operation
    timed out" errors even on small files and with generous timeouts.
    """
    import tempfile

    content_type = getattr(file_storage, "content_type", None) or "application/octet-stream"

    suffix = os.path.splitext(filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        temp_path = tmp.name

    try:
        if hasattr(file_storage, "save"):
            # Flask FileStorage object (has .save(path))
            file_storage.save(temp_path)
        else:
            # Plain file-like object (e.g. io.BytesIO from processed images)
            if hasattr(file_storage, "seek"):
                file_storage.seek(0)
            data = file_storage.read()
            with open(temp_path, "wb") as f:
                f.write(data)

        upload_url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{filename}"
        headers = {
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "apikey": SUPABASE_KEY,
            "Content-Type": content_type,
            "x-upsert": "true",
        }

        with open(temp_path, "rb") as f:
            file_bytes = f.read()

        last_error = None
        response = None
        for attempt in range(2):
            try:
                response = requests.post(
                    upload_url,
                    headers=headers,
                    data=file_bytes,
                    timeout=30,
                )
                last_error = None
                break
            except requests.exceptions.RequestException as e:
                last_error = e

        if last_error is not None:
            raise last_error

        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"Supabase upload failed: {response.status_code} {response.text}"
            )

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    return supabase.storage.from_(SUPABASE_BUCKET).get_public_url(filename)


def delete_file(filename):
    supabase.storage.from_(SUPABASE_BUCKET).remove([filename])