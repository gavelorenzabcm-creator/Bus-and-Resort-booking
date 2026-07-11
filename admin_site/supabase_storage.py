import os
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "uploads")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is missing from .env"
    )

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def upload_file(file_storage, filename):
    try:
        print("SUPABASE_URL =", SUPABASE_URL)
        print("BUCKET =", SUPABASE_BUCKET)

        file_storage.seek(0)
        data = file_storage.read()

        content_type = getattr(
            file_storage,
            "content_type",
            "application/octet-stream",
        )

        result = supabase.storage.from_(SUPABASE_BUCKET).upload(
            path=filename,
            file=data,
            file_options={
                "content-type": content_type,
                "upsert": True,
            },
        )

        print("UPLOAD RESULT:", result)

        url = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(filename)

        print("PUBLIC URL:", url)

        return url

    except Exception as e:
        print("UPLOAD ERROR:", repr(e))
        raise

    return supabase.storage.from_(SUPABASE_BUCKET).get_public_url(filename)


def delete_file(filename):
    supabase.storage.from_(SUPABASE_BUCKET).remove([filename])