import os
import hmac
from flask import Blueprint, jsonify, request, current_app
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from config.database import supabase

checkin_bp = Blueprint("checkin", __name__)

THAI_TZ = ZoneInfo("Asia/Bangkok")


def require_scanner_agent():
    expected = os.getenv("SCANNER_AGENT_TOKEN", "")
    supplied = request.headers.get("X-Scanner-Agent-Token", "")
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))


# =========================================================
# Helper: Get Active Semester
# =========================================================

def get_active_semester():
    response = (
        supabase.table("semesters")
        .select("id, semester_name, start_date, end_date")
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    semester = response.data[0]
    semester["start_date"] = date.fromisoformat(str(semester["start_date"]))
    semester["end_date"] = date.fromisoformat(str(semester["end_date"]))
    return semester


def get_semester_date_range():
    semester = get_active_semester()
    if not semester:
        return None
    return semester["start_date"], semester["end_date"]


# =========================================================
# Helper: Get Current Subject
# =========================================================

def get_current_subject():
    now = datetime.now(THAI_TZ)
    semester = get_active_semester()
    if not semester:
        return None
    if not (semester["start_date"] <= now.date() <= semester["end_date"]):
        return None

    response = (
        supabase.table("subjects")
        .select("id, code, name, class_days, start_time, end_time, late_after_minutes")
        .execute()
    )
    weekday = now.strftime("%A")
    current_time = now.time().replace(tzinfo=None)
    matches = []

    for subject in response.data or []:
        class_days = subject.get("class_days") or []
        if isinstance(class_days, str):
            class_days = [day.strip() for day in class_days.replace(";", ",").split(",") if day.strip()]
        class_days = [str(day).strip().capitalize() for day in class_days]
        if weekday not in class_days:
            continue
        try:
            start_text = str(subject.get("start_time") or "").strip()
            end_text = str(subject.get("end_time") or "").strip()
            start_time = datetime.strptime(start_text[:8], "%H:%M:%S" if len(start_text) >= 8 else "%H:%M").time()
            end_time = datetime.strptime(end_text[:8], "%H:%M:%S" if len(end_text) >= 8 else "%H:%M").time()
        except ValueError:
            continue
        if start_time <= current_time <= end_time:
            matches.append(subject)

    if not matches:
        return None
    matches.sort(key=lambda subject: str(subject.get("start_time") or ""), reverse=True)
    return matches[0]


def normalize_class_days(value):
    if isinstance(value, str):
        value = value.replace(";", ",").split(",")
    return {str(day).strip().capitalize() for day in (value or []) if str(day).strip()}


def parse_subject_end_time(value):
    text = str(value or "").strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text[:8], fmt).time()
        except ValueError:
            continue
    return None


def parse_subject_start_time(value):
    text = str(value or "").strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text[:8], fmt).time()
        except ValueError:
            continue
    return None


# =========================================================
# GET: Current Subject
# =========================================================

@checkin_bp.route("/api/current-subject", methods=["GET"])
def api_current_subject():
    try:
        subject = get_current_subject()
        if not subject:
            return jsonify({"active": False}), 200
        return jsonify({
            "active": True,
            "id": subject.get("id"),
            "code": subject.get("code"),
            "name": subject.get("name"),
            "class_days": subject.get("class_days") or [],
            "start_time": str(subject.get("start_time") or "")[:5],
            "end_time": str(subject.get("end_time") or "")[:5],
            "late_after_minutes": subject.get("late_after_minutes") or 0
        }), 200
    except Exception:
        current_app.logger.exception("Unable to retrieve current subject")
        return jsonify({"success": False, "message": "ไม่สามารถดึงข้อมูลวิชาปัจจุบันได้"}), 500


# =========================================================
# GET: Active Semester for CheckIn
# =========================================================

@checkin_bp.route("/api/checkin/semester", methods=["GET"])
def api_checkin_semester():
    try:
        semester = get_active_semester()
        if not semester:
            return jsonify({"success": True, "active": False, "semester": None}), 200
        today = datetime.now(THAI_TZ).date()
        is_in_period = semester["start_date"] <= today <= semester["end_date"]
        return jsonify({
            "success": True,
            "active": True,
            "in_period": is_in_period,
            "semester": {
                "id": semester["id"],
                "semester_name": semester["semester_name"],
                "start_date": semester["start_date"].isoformat(),
                "end_date": semester["end_date"].isoformat()
            }
        }), 200
    except Exception:
        current_app.logger.exception("Unable to retrieve check-in semester")
        return jsonify({"success": False, "message": "ไม่สามารถดึงข้อมูลภาคเรียนได้"}), 500


# =========================================================
# Scanner Agent: Get registered fingerprint templates
# =========================================================

@checkin_bp.route("/api/checkin/fingerprint-templates", methods=["GET"])
def api_fingerprint_templates():
    if not require_scanner_agent():
        return jsonify({"success": False, "message": "Scanner Agent authentication failed"}), 401
    try:
        response = (
            supabase.table("users")
            .select("id, fingerprint_id, fingerprint_template")
            .not_.is_("fingerprint_template", "null")
            .execute()
        )
        templates = []
        for row in response.data or []:
            template = row.get("fingerprint_template")
            fingerprint_id = row.get("fingerprint_id") or row.get("id")
            if not template or fingerprint_id is None:
                continue
            try:
                numeric_id = int(fingerprint_id)
            except (TypeError, ValueError):
                current_app.logger.warning("Invalid fingerprint_id for user id=%s", row.get("id"))
                continue
            templates.append({
                "user_id": row.get("id"),
                "fingerprint_id": numeric_id,
                "template": template
            })
        return jsonify({"success": True, "templates": templates, "count": len(templates)}), 200
    except Exception:
        current_app.logger.exception("Unable to retrieve fingerprint templates")
        return jsonify({"success": False, "message": "ไม่สามารถโหลดข้อมูลลายนิ้วมือได้"}), 500


# =========================================================
# Scanner Agent: Record a successful fingerprint match
# =========================================================

@checkin_bp.route("/api/checkin/record", methods=["POST"])
def api_record_checkin():
    if not require_scanner_agent():
        return jsonify({"success": False, "message": "Scanner Agent authentication failed"}), 401

    payload = request.get_json(silent=True) or {}
    try:
        fingerprint_id = str(int(payload.get("fingerprint_id")))
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "fingerprint_id ไม่ถูกต้อง"}), 400

    try:
        user_response = (
            supabase.table("users")
            .select("id, student_id, full_name, department, fingerprint_id")
            .eq("fingerprint_id", fingerprint_id)
            .limit(1)
            .execute()
        )
        if not user_response.data:
            return jsonify({"success": False, "message": "ไม่พบผู้ใช้ที่ตรงกับลายนิ้วมือนี้"}), 404

        user = user_response.data[0]
        now = datetime.now(THAI_TZ)
        semester = get_active_semester()
        subject = get_current_subject() if semester else None

        if subject:
            start_time = parse_subject_start_time(subject.get("start_time"))
            late_after = int(subject.get("late_after_minutes") or 0)
            late_time = (
                datetime.combine(now.date(), start_time) + timedelta(minutes=late_after)
                if start_time else None
            )
            status = "late" if late_time and now.replace(tzinfo=None) > late_time else "on_time"
            subject_id = subject.get("id")
        else:
            status = "no_class"
            subject_id = None

        # Prevent duplicate check-ins for the same user and subject on the same Thai date.
        day_start = datetime.combine(now.date(), datetime.min.time(), tzinfo=THAI_TZ)
        day_end = datetime.combine(now.date(), datetime.max.time(), tzinfo=THAI_TZ)
        duplicate_query = (
            supabase.table("scan_logs")
            .select("id, scanned_at, status")
            .eq("user_id", user["id"])
            .gte("scanned_at", day_start.isoformat())
            .lte("scanned_at", day_end.isoformat())
        )
        if subject_id is not None:
            duplicate_query = duplicate_query.eq("subject_id", subject_id)
        else:
            duplicate_query = duplicate_query.is_("subject_id", "null")
        duplicate = duplicate_query.limit(1).execute()

        if duplicate.data:
            existing = duplicate.data[0]
            return jsonify({
                "success": True,
                "already_checked_in": True,
                "message": "บันทึกเวลาเข้าเรียนแล้วในวันนี้",
                "user": {
                    "id": user["id"], "student_id": user.get("student_id"),
                    "full_name": user.get("full_name"), "department": user.get("department")
                },
                "attendance": {
                    "status": existing.get("status"),
                    "scanned_at": existing.get("scanned_at"),
                    "subject_id": subject_id
                }
            }), 200

        insert_data = {
            "user_id": user["id"],
            "fingerprint_id": fingerprint_id,
            "subject_id": subject_id,
            "semester_id": semester.get("id") if semester else None,
            "scanned_at": now.isoformat(),
            "status": status
        }
        insert_response = supabase.table("scan_logs").insert(insert_data).execute()
        saved = (insert_response.data or [{}])[0]

        return jsonify({
            "success": True,
            "already_checked_in": False,
            "message": "เช็คชื่อสำเร็จ" if status in ("on_time", "late") else "บันทึกการสแกนแล้ว ขณะนี้ไม่มีรายวิชาที่กำลังเรียน",
            "user": {
                "id": user["id"], "student_id": user.get("student_id"),
                "full_name": user.get("full_name"), "department": user.get("department")
            },
            "attendance": {
                "id": saved.get("id"),
                "status": status,
                "scanned_at": saved.get("scanned_at") or now.isoformat(),
                "subject_id": subject_id,
                "subject_name": subject.get("name") if subject else None
            }
        }), 200
    except Exception:
        current_app.logger.exception("Unable to record fingerprint check-in")
        return jsonify({"success": False, "message": "ไม่สามารถบันทึกเวลาเข้าเรียนได้"}), 500


# =========================================================
# GET: Recent Scan Logs
# =========================================================

@checkin_bp.route("/api/scans/recent", methods=["GET"])
def api_recent_scans():
    try:
        limit = request.args.get("limit", default=50, type=int)
        limit = max(1, min(limit, 100))
        statistics = get_attendance_statistics()
        response = (
            supabase.table("scan_logs")
            .select("""
                id, user_id, scanned_at, status, fingerprint_id, subject_id,
                users (student_id, full_name, department),
                subjects (id, code, name)
            """)
            .order("scanned_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = []
        for row in response.data or []:
            user = row.get("users") or {}
            subject = row.get("subjects") or {}
            user_id = row.get("user_id")
            subject_id = row.get("subject_id")
            stats = statistics.get((str(user_id), str(subject_id)), {
                "attended_count": 0, "absent_count": 0
            })
            rows.append({
                "id": row.get("id"),
                "scanned_at": row.get("scanned_at"),
                "status": row.get("status"),
                "fingerprint_id": row.get("fingerprint_id"),
                "user_id": user_id,
                "student_id": user.get("student_id"),
                "full_name": user.get("full_name"),
                "department": user.get("department"),
                "subject_id": subject_id,
                "subject_code": subject.get("code"),
                "subject_name": subject.get("name"),
                "attended_count": stats["attended_count"],
                "absent_count": stats["absent_count"]
            })
        return jsonify(rows), 200
    except Exception:
        current_app.logger.exception("Unable to retrieve recent scans")
        return jsonify({"success": False, "message": "ไม่สามารถดึงรายการสแกนล่าสุดได้"}), 500


# =========================================================
# Helper: Get Attendance Statistics
# =========================================================

def get_attendance_statistics():
    now = datetime.now(THAI_TZ)
    today = now.date()
    semester_range = get_semester_date_range()
    if not semester_range:
        return {}
    semester_start, semester_end = semester_range
    statistics_end = min(today, semester_end)
    if today < semester_start:
        return {}

    subjects_response = supabase.table("subjects").select(
        "id, section_id, class_days, end_time"
    ).execute()
    subjects = subjects_response.data or []

    users_response = supabase.table("users").select("id, section_id").execute()
    users = users_response.data or []

    start_datetime = datetime.combine(semester_start, datetime.min.time(), tzinfo=THAI_TZ)
    end_datetime = datetime.combine(statistics_end, datetime.max.time(), tzinfo=THAI_TZ)

    scan_logs = []
    offset = 0
    page_size = 1000
    while True:
        response = (
            supabase.table("scan_logs")
            .select("user_id, subject_id, scanned_at, status")
            .gte("scanned_at", start_datetime.isoformat())
            .lte("scanned_at", end_datetime.isoformat())
            .order("scanned_at", desc=False)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = response.data or []
        scan_logs.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size

    attended_dates = {}
    for log in scan_logs:
        if log.get("status") not in ("on_time", "late"):
            continue
        user_id = log.get("user_id")
        subject_id = log.get("subject_id")
        scanned_at = log.get("scanned_at")
        if user_id is None or subject_id is None or not scanned_at:
            continue
        try:
            scanned_datetime = datetime.fromisoformat(str(scanned_at).replace("Z", "+00:00"))
            if scanned_datetime.tzinfo is None:
                scanned_datetime = scanned_datetime.replace(tzinfo=THAI_TZ)
            scanned_date = scanned_datetime.astimezone(THAI_TZ).date()
        except (ValueError, TypeError):
            continue
        key = (str(user_id), str(subject_id))
        attended_dates.setdefault(key, set()).add(scanned_date)

    statistics = {}
    for subject in subjects:
        subject_id = subject.get("id")
        section_id = subject.get("section_id")
        class_days = normalize_class_days(subject.get("class_days"))
        end_time = parse_subject_end_time(subject.get("end_time"))
        if not class_days or not end_time:
            continue
        class_dates = set()
        current_date = semester_start
        while current_date <= statistics_end:
            weekday = current_date.strftime("%A")
            if weekday in class_days:
                is_past_class = current_date < today
                if current_date == today:
                    is_past_class = now.time().replace(tzinfo=None) >= end_time
                if is_past_class:
                    class_dates.add(current_date)
            current_date += timedelta(days=1)

        section_users = [
            user for user in users
            if str(user.get("section_id")) == str(section_id)
        ]
        for user in section_users:
            user_id = user.get("id")
            key = (str(user_id), str(subject_id))
            attended = attended_dates.get(key, set()).intersection(class_dates)
            statistics[key] = {
                "attended_count": len(attended),
                "absent_count": len(class_dates) - len(attended)
            }
    return statistics
