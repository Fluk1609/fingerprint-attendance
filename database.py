"""
database.py
-----------
จัดการฐานข้อมูล Supabase
สำหรับระบบเช็คชื่อด้วยลายนิ้วมือ
"""

import os
from datetime import datetime

from dotenv import load_dotenv
from supabase import create_client, Client


# =========================================================
# Supabase Connection
# =========================================================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL:
    raise RuntimeError("ไม่พบ SUPABASE_URL ในไฟล์ .env")

if not SUPABASE_KEY:
    raise RuntimeError("ไม่พบ SUPABASE_KEY ในไฟล์ .env")


supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# =========================================================
# Init DB
# =========================================================

def init_db():
    """
    Supabase ไม่ต้องสร้าง database จาก Python
    เพราะสร้าง table ผ่าน Supabase SQL Editor แล้ว
    """

    try:
        supabase.table("users").select("id").limit(1).execute()
        print("✅ Supabase database พร้อมใช้งาน")
    except Exception as exc:
        print(f"❌ ไม่สามารถเชื่อมต่อ Supabase: {exc}")
        raise


# =========================================================
# Users
# =========================================================

def add_user(
    student_id,
    full_name,
    department,
    fingerprint_id
):
    """
    เพิ่มผู้ใช้งาน
    """

    data = {
        "student_id": student_id,
        "full_name": full_name,
        "department": department,
        "fingerprint_id": fingerprint_id,
        "created_at": datetime.now().isoformat(
            timespec="seconds"
        ),
    }

    response = (
        supabase
        .table("users")
        .insert(data)
        .execute()
    )

    return response.data


def get_all_users():
    """
    ดึงผู้ใช้งานทั้งหมด
    """

    response = (
        supabase
        .table("users")
        .select("*")
        .order("full_name")
        .execute()
    )

    return response.data or []


def get_user_by_fingerprint(fingerprint_id):
    """
    ค้นหาผู้ใช้จาก fingerprint_id
    """

    response = (
        supabase
        .table("users")
        .select("*")
        .eq("fingerprint_id", fingerprint_id)
        .limit(1)
        .execute()
    )

    if response.data:
        return response.data[0]

    return None


def delete_user(user_id):
    """
    ลบผู้ใช้งาน
    """

    response = (
        supabase
        .table("users")
        .delete()
        .eq("id", user_id)
        .execute()
    )

    return response.data


# =========================================================
# Scan Logs
# =========================================================

def add_scan_log(
    fingerprint_id,
    user_id,
    status,
    scanned_at=None
):
    """
    บันทึกประวัติการสแกน
    """

    data = {
        "fingerprint_id": fingerprint_id,
        "user_id": user_id,
        "status": status,
        "scanned_at": (
            scanned_at
            or datetime.now().isoformat(
                timespec="seconds"
            )
        ),
    }

    response = (
        supabase
        .table("scan_logs")
        .insert(data)
        .execute()
    )

    return response.data


def get_recent_logs(limit=50):
    """
    ดึงประวัติการสแกนล่าสุด
    """

    response = (
        supabase
        .table("scan_logs")
        .select(
            """
            id,
            scanned_at,
            status,
            fingerprint_id,
            users (
                student_id,
                full_name,
                department
            )
            """
        )
        .order("scanned_at", desc=True)
        .limit(limit)
        .execute()
    )

    rows = []

    for row in response.data or []:

        user = row.get("users") or {}

        rows.append({
            "id": row.get("id"),
            "scanned_at": row.get("scanned_at"),
            "status": row.get("status"),
            "fingerprint_id": row.get("fingerprint_id"),
            "student_id": user.get("student_id"),
            "full_name": user.get("full_name"),
            "department": user.get("department"),
        })

    return rows


def get_logs_in_range(
    start_date,
    end_date,
    user_id=None
):
    """
    ดึงประวัติการสแกนตามช่วงวันที่

    start_date:
        YYYY-MM-DD

    end_date:
        YYYY-MM-DD
    """

    query = (
        supabase
        .table("scan_logs")
        .select(
            """
            scanned_at,
            status,
            fingerprint_id,
            user_id,
            users (
                student_id,
                full_name,
                department
            )
            """
        )
        .gte(
            "scanned_at",
            f"{start_date}T00:00:00"
        )
        .lt(
            "scanned_at",
            f"{end_date}T23:59:59"
        )
        .order("scanned_at")
    )

    if user_id:
        query = query.eq(
            "user_id",
            user_id
        )

    response = query.execute()

    rows = []

    for row in response.data or []:

        user = row.get("users") or {}

        rows.append({
            "scanned_at": row.get("scanned_at"),
            "status": row.get("status"),
            "fingerprint_id": row.get("fingerprint_id"),
            "student_id": user.get("student_id"),
            "full_name": user.get("full_name"),
            "department": user.get("department"),
        })

    return rows