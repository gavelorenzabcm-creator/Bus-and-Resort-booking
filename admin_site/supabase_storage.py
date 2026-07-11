import os
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "uploads")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def upload_file(file_storage, filename):
    file_storage.seek(0)

    data = file_storage.read()

    supabase.storage.from_(SUPABASE_BUCKET).upload(
        path=filename,
        file=data,
        file_options={
            "content-type": file_storage.content_type,
            "upsert": "true",
        },
    )

    return supabase.storage.from_(SUPABASE_BUCKET).get_public_url(filename)


def delete_file(filename):
    supabase.storage.from_(SUPABASE_BUCKET).remove([filename])