import os
from datetime import datetime

from dotenv import load_dotenv
from supabase import create_client, Client
import base64

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

def init_db():

    try:
        supabase.table("users").select("id").limit(1).execute()
        print("✅ Supabase database พร้อมใช้งาน")
    except Exception as exc:
        print(f"❌ ไม่สามารถเชื่อมต่อ Supabase: {exc}")
        raise


def add_user(
    student_id,
    full_name,
    department,
    fingerprint_id,
    section=None,
    created_at=None,
    section_id=None,
):

    data = {
        "student_id": str(student_id).strip(),
        "full_name": str(full_name).strip(),
        "department": department or None,
        "fingerprint_id": str(fingerprint_id).strip(),
        "created_at": created_at or datetime.now().astimezone().isoformat(
            timespec="seconds"
        ),
    }

    if section_id is not None:
        data["section_id"] = section_id
    elif section is not None:
        data["section"] = section

    response = (
        supabase
        .table("users")
        .insert(data)
        .execute()
    )

    return response.data


def get_all_users():
    response = (
        supabase
        .table("users")
        .select("*")
        .order("full_name")
        .execute()
    )

    return response.data or []


def get_user_by_fingerprint(fingerprint_id):
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
    response = (
        supabase
        .table("users")
        .delete()
        .eq("id", user_id)
        .execute()
    )

    return response.data


def import_users_from_excel(rows):
    result = {
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "errors": []
    }

    for index, row in enumerate(rows, start=2):
        student_id = str(row.get("student_id") or "").strip()
        full_name = str(row.get("full_name") or "").strip()
        department = str(row.get("department") or "").strip() or None
        section_id = row.get("section_id")
        section = str(row.get("section") or "").strip() or None

        if not student_id or not full_name:
            result["skipped"] += 1
            result["errors"].append({
                "row": index,
                "message": "ไม่มีรหัสนักศึกษาหรือชื่อ-นามสกุล"
            })
            continue

        fingerprint_id = student_id

        try:
            existing_student = (
                supabase.table("users")
                .select("id, fingerprint_id")
                .eq("student_id", student_id)
                .limit(1)
                .execute()
            )

            if existing_student.data:
                existing = existing_student.data[0]
                update_data = {
                    "full_name": full_name,
                    "department": department,
                    "fingerprint_id": fingerprint_id,
                }
                if section_id is not None:
                    update_data["section_id"] = section_id
                elif section is not None:
                    update_data["section"] = section
                (
                    supabase.table("users")
                    .update(update_data)
                    .eq("id", existing["id"])
                    .execute()
                )
                result["updated"] += 1
                continue

            existing_fingerprint = (
                supabase.table("users")
                .select("id, student_id")
                .eq("fingerprint_id", fingerprint_id)
                .limit(1)
                .execute()
            )
            if existing_fingerprint.data:
                result["skipped"] += 1
                result["errors"].append({
                    "row": index,
                    "message": f"fingerprint_id {fingerprint_id} ถูกใช้โดย student_id อื่นแล้ว"
                })
                continue

            add_user(
                student_id=student_id,
                full_name=full_name,
                department=department,
                fingerprint_id=fingerprint_id,
                section=section,
                section_id=section_id
            )
            result["inserted"] += 1

        except Exception as exc:
            result["errors"].append({
                "row": index,
                "message": str(exc)
            })

    return result

def has_fingerprint_template(fingerprint_id):

    response = (
        supabase
        .table("users")
        .select("fingerprint_template")
        .eq("fingerprint_id", str(fingerprint_id))
        .limit(1)
        .execute()
    )

    if not response.data:
        return False

    return bool(
        response.data[0].get("fingerprint_template")
    )


def get_fingerprint_template(fingerprint_id):

    response = (
        supabase
        .table("users")
        .select("fingerprint_template")
        .eq("fingerprint_id", str(fingerprint_id))
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    template = response.data[0].get("fingerprint_template")

    if not template:
        return None

    return base64.b64decode(template, validate=True)


def get_all_fingerprint_templates():

    response = (
        supabase
        .table("users")
        .select("fingerprint_id, fingerprint_template")
        .not_.is_("fingerprint_template", "null")
        .execute()
    )

    templates = {}

    for row in response.data or []:
        fingerprint_id = row.get("fingerprint_id")
        template = row.get("fingerprint_template")

        if fingerprint_id is None or not template:
            continue

        templates[str(fingerprint_id)] = base64.b64decode(
            template,
            validate=True
        )

    return templates


def update_fingerprint_template(fingerprint_id, template):

    if isinstance(template, bytes):
        encoded_template = base64.b64encode(
            template
        ).decode("ascii")

    elif isinstance(template, str):
        # รองรับกรณีต้นทางส่ง Base64 string มาแล้ว
        base64.b64decode(template, validate=True)
        encoded_template = template

    else:
        raise TypeError(
            "template ต้องเป็น bytes หรือ Base64 string"
        )

    response = (
        supabase
        .table("users")
        .update({
            "fingerprint_template": encoded_template
        })
        .eq("fingerprint_id", str(fingerprint_id))
        .execute()
    )

    if not response.data:
        raise ValueError(
            f"ไม่พบผู้ใช้ fingerprint_id={fingerprint_id} "
            "ใน Supabase"
        )

    return response.data

def add_scan_log(
    fingerprint_id,
    user_id,
    status,
    scanned_at=None,
    subject_id=None,
):
    data = {
        "fingerprint_id": str(fingerprint_id),
        "user_id": user_id,
        "status": status,
        "scanned_at": scanned_at or datetime.now().astimezone().isoformat(timespec="seconds"),
        "subject_id": subject_id,
    }
    response = supabase.table("scan_logs").insert(data).execute()
    return response.data


def get_recent_logs(limit=50):
    response = (
        supabase
        .table("scan_logs")
        .select(
            """
            id,
            scanned_at,
            status,
            fingerprint_id,
            subject_id,
            users (student_id, full_name, department),
            subjects (id, code, name)
            """
        )
        .order("scanned_at", desc=True)
        .limit(limit)
        .execute()
    )

    rows = []
    for row in response.data or []:
        user = row.get("users") or {}
        subject = row.get("subjects") or {}
        rows.append({
            "id": row.get("id"),
            "scanned_at": row.get("scanned_at"),
            "status": row.get("status"),
            "fingerprint_id": row.get("fingerprint_id"),
            "student_id": user.get("student_id"),
            "full_name": user.get("full_name"),
            "department": user.get("department"),
            "subject_id": row.get("subject_id"),
            "subject_code": subject.get("code"),
            "subject_name": subject.get("name"),
        })
    return rows


def get_logs_in_range(
    start_date,
    end_date,
    user_id=None
):

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