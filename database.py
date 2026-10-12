"""
database.py
-----------
จัดการฐานข้อมูล Supabase
สำหรับระบบเช็คชื่อด้วยลายนิ้วมือ
"""

import os
import base64
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
    (ดูไฟล์ supabase_schema.sql สำหรับคำสั่งสร้าง/อัปเดตตารางทั้งหมด
    รวมถึงคอลัมน์ fingerprint_template และ heart_rate ที่ต้องรันเพิ่มถ้ายังไม่มี)
    """

    try:
        supabase.table("users").select("id, fingerprint_template").limit(1).execute()
        supabase.table("scan_logs").select("id, heart_rate").limit(1).execute()
        print("✅ Supabase database พร้อมใช้งาน (มีคอลัมน์ fingerprint_template และ heart_rate แล้ว)")
    except Exception as exc:
        print(f"❌ ไม่สามารถเชื่อมต่อ Supabase หรือยังไม่ได้รัน migration: {exc}")
        print("   กรุณารันคำสั่งใน supabase_schema.sql ผ่าน Supabase SQL Editor ก่อน")
        raise


# =========================================================
# Users
# =========================================================

def add_user(
    student_id,
    full_name,
    department,
    fingerprint_id=None
):
    """
    เพิ่มผู้ใช้งาน (fingerprint_id ไม่บังคับ เว้นว่างได้ถ้าจะลงทะเบียนนิ้วทีหลังด้วย zkteco_enroll.py)
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


def create_user_placeholder(
    student_id,
    full_name,
    department
):
    """
    ใช้โดย zkteco_enroll.py: สร้างข้อมูลผู้ใช้ก่อน (ยังไม่มีลายนิ้วมือ) เพื่อให้ได้ id
    มาใช้เป็น fingerprint_id ตอนลงทะเบียนกับเครื่อง ZKTeco ต่อ
    คืนค่า id (int) ของผู้ใช้ที่สร้างใหม่
    """

    data = {
        "student_id": student_id,
        "full_name": full_name,
        "department": department,
        "fingerprint_id": None,
        "fingerprint_template": None,
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

    return response.data[0]["id"]


def set_user_fingerprint(
    user_id,
    fingerprint_id,
    fingerprint_template_bytes
):
    """
    ใช้โดย zkteco_enroll.py: ผูกเทมเพลตลายนิ้วมือที่สแกนได้เข้ากับผู้ใช้ที่สร้างไว้
    เก็บเทมเพลตเป็น base64 text เพราะ Supabase REST API (PostgREST) รับ JSON
    ไม่รับ binary bytes ตรงๆ จึงต้องเข้ารหัสเป็นข้อความก่อนบันทึก
    """

    template_b64 = base64.b64encode(fingerprint_template_bytes).decode("ascii")

    data = {
        "fingerprint_id": fingerprint_id,
        "fingerprint_template": template_b64,
    }

    response = (
        supabase
        .table("users")
        .update(data)
        .eq("id", user_id)
        .execute()
    )

    return response.data


def get_users_with_templates():
    """
    ใช้โดย scanner.py ตอนเริ่มทำงาน: โหลดเทมเพลตลายนิ้วมือทั้งหมดเข้าหน่วยความจำเครื่อง ZKTeco ใหม่
    คืนค่าเป็น list ของ dict ที่มี fingerprint_template ถอดรหัส base64 กลับเป็น bytes แล้ว
    """

    response = (
        supabase
        .table("users")
        .select("id, fingerprint_id, fingerprint_template")
        .not_.is_("fingerprint_template", "null")
        .execute()
    )

    rows = []

    for row in response.data or []:
        template_b64 = row.get("fingerprint_template")
        if not template_b64:
            continue
        rows.append({
            "id": row.get("id"),
            "fingerprint_id": row.get("fingerprint_id"),
            "fingerprint_template": base64.b64decode(template_b64),
        })

    return rows


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
    scanned_at=None,
    heart_rate=None
):
    """
    บันทึกประวัติการสแกน (heart_rate ไม่บังคับ มีเฉพาะเครื่องที่ต่อเซนเซอร์วัดชีพจรไว้)
    """

    data = {
        "fingerprint_id": fingerprint_id,
        "user_id": user_id,
        "status": status,
        "heart_rate": heart_rate,
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
            heart_rate,
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
            "heart_rate": row.get("heart_rate"),
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
            heart_rate,
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
            "heart_rate": row.get("heart_rate"),
            "student_id": user.get("student_id"),
            "full_name": user.get("full_name"),
            "department": user.get("department"),
        })

    return rows