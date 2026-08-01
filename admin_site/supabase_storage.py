import os
import tempfile
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "uploads")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is missing from .env"
    )

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
import storage3
print("storage3 version:", getattr(storage3, "__version__", "unknown"))


def upload_file(file_storage, filename):
    import os
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

        result = supabase.storage.from_(SUPABASE_BUCKET).upload(
            path=filename,
            file=temp_path,
            file_options={
                "content-type": content_type,
                "upsert": "true",
            },
        )
    except Exception as e:
        raise
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    return supabase.storage.from_(SUPABASE_BUCKET).get_public_url(filename)


def delete_file(filename):
    supabase.storage.from_(SUPABASE_BUCKET).remove([filename])