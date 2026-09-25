import os

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_PUBLISHABLE_KEY")

if not url:
    raise Exception("❌ ไม่พบ SUPABASE_URL")

if not key:
    raise Exception("❌ ไม่พบ SUPABASE_PUBLISHABLE_KEY")

print("URL:", url)
print("กำลังเชื่อมต่อ Supabase...")

supabase = create_client(url, key)

result = (
    supabase
    .table("users")
    .select("*")
    .execute()
)

print("✅ เชื่อมต่อ Supabase สำเร็จ")
print("Users:", result.data)