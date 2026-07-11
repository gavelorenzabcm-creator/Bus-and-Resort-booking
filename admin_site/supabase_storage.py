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
    file_storage.stream.seek(0)

    result = supabase.storage.from_(SUPABASE_BUCKET).upload(
        path=filename,
        file=file_storage.stream,
        file_options={
            "content-type": file_storage.content_type,
            "upsert": "true",
        },
    )

    return supabase.storage.from_(SUPABASE_BUCKET).get_public_url(filename)

def delete_file(filename):
    supabase.storage.from_(SUPABASE_BUCKET).remove([filename])