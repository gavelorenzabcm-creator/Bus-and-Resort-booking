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

    print("===== UPLOAD DEBUG =====")
    print("filename:", filename)
    print("content_type:", file_storage.content_type)
    print("stream:", file_storage.stream)

    suffix = os.path.splitext(filename)[1]

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        file_storage.save(tmp.name)
        temp_path = tmp.name

    print("temp path:", temp_path)
    print("temp size:", os.path.getsize(temp_path))

    try:
        result = supabase.storage.from_(SUPABASE_BUCKET).upload(
            path=filename,
            file=temp_path,
            file_options={
                "content-type": file_storage.content_type,
                "upsert": "true",
        },
    )

        print("UPLOAD SUCCESS:", result)

    except Exception as e:
        print("UPLOAD FAILED")
        print(type(e))
        print(repr(e))
        raise

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    return supabase.storage.from_(SUPABASE_BUCKET).get_public_url(filename)


def delete_file(filename):
    supabase.storage.from_(SUPABASE_BUCKET).remove([filename])