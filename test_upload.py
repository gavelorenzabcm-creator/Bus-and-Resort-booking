from dotenv import load_dotenv
load_dotenv()

import os
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

print("URL:", SUPABASE_URL)
print("KEY FOUND:", bool(SUPABASE_KEY))

client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Create a test file
with open("hello.txt", "w") as f:
    f.write("Hello from ChatGPT!")

# Upload it
with open("hello.txt", "rb") as f:
    result = client.storage.from_("uploads").upload(
        path="hello.txt",
        file=f,
        file_options={"upsert": "true"},
    )

print("Upload Result:")
print(result)

print("Public URL:")
print(client.storage.from_("uploads").get_public_url("hello.txt"))