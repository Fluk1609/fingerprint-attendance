import os
from dotenv import load_dotenv
from supabase import create_client, Client

# โหลด Environment Variables จากไฟล์ .env ที่ Root Project
ROOT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../..")
)

load_dotenv(os.path.join(ROOT_DIR, ".env"))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(
        "Missing SUPABASE_URL or SUPABASE_KEY in root .env"
    )

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)