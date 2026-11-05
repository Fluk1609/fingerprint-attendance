from flask import Blueprint, jsonify, request, current_app
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from config.database import supabase

checkin_bp = Blueprint("checkin", __name__)

THAI_TZ = ZoneInfo("Asia/Bangkok")


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

    semester["start_date"] = date.fromisoformat(
        str(semester["start_date"])
    )

    semester["end_date"] = date.fromisoformat(
        str(semester["end_date"])
    )

    return semester


# =========================================================
# Helper: Get Semester Date Range
# =========================================================

def get_semester_date_range():
    semester = get_active_semester()

    if not semester:
        return None

    return (
        semester["start_date"],
        semester["end_date"]
    )


# =========================================================
# Helper: Get Current Subject
# =========================================================

def get_current_subject():
    now = datetime.now(THAI_TZ)

    semester = get_active_semester()

    if not semester:
        return None

    # ตรวจสอบวันที่อยู่ในช่วงภาคเรียน
    if not (
        semester["start_date"]
        <= now.date()
        <= semester["end_date"]
    ):
        return None

    response = (
        supabase.table("subjects")
        .select(
            "id, code, name, class_days, "
            "start_time, end_time, late_after_minutes"
        )
        .execute()
    )

    weekday = now.strftime("%A")
    current_time = now.time().replace(tzinfo=None)

    matches = []

    for subject in response.data or []:
        class_days = subject.get("class_days") or []

        if isinstance(class_days, str):
            class_days = [
                day.strip()
                for day in class_days.replace(";", ",").split(",")
                if day.strip()
            ]

        class_days = [
            str(day).strip().capitalize()
            for day in class_days
        ]

        if weekday not in class_days:
            continue

        try:
            start_text = str(
                subject.get("start_time") or ""
            ).strip()

            end_text = str(
                subject.get("end_time") or ""
            ).strip()

            start_time = datetime.strptime(
                start_text[:8],
                "%H:%M:%S" if len(start_text) >= 8 else "%H:%M"
            ).time()

            end_time = datetime.strptime(
                end_text[:8],
                "%H:%M:%S" if len(end_text) >= 8 else "%H:%M"
            ).time()

        except ValueError:
            continue

        if start_time <= current_time <= end_time:
            matches.append(subject)

    if not matches:
        return None

    matches.sort(
        key=lambda subject: str(
            subject.get("start_time") or ""
        ),
        reverse=True
    )

    return matches[0]


# =========================================================
# Helper: Normalize Class Days
# =========================================================

def normalize_class_days(value):
    if isinstance(value, str):
        value = value.replace(";", ",").split(",")

    return {
        str(day).strip().capitalize()
        for day in (value or [])
        if str(day).strip()
    }


# =========================================================
# Helper: Parse Subject End Time
# =========================================================

def parse_subject_end_time(value):
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
            return jsonify({
                "active": False
            }), 200

        return jsonify({
            "active": True,
            "id": subject.get("id"),
            "code": subject.get("code"),
            "name": subject.get("name"),
            "class_days": subject.get("class_days") or [],
            "start_time": str(
                subject.get("start_time") or ""
            )[:5],
            "end_time": str(
                subject.get("end_time") or ""
            )[:5],
            "late_after_minutes": (
                subject.get("late_after_minutes") or 0
            )
        }), 200

    except Exception:
        current_app.logger.exception(
            "Unable to retrieve current subject"
        )

        return jsonify({
            "success": False,
            "message": "ไม่สามารถดึงข้อมูลวิชาปัจจุบันได้"
        }), 500


# =========================================================
# GET: Active Semester for CheckIn
# =========================================================

@checkin_bp.route("/api/checkin/semester", methods=["GET"])
def api_checkin_semester():
    try:
        semester = get_active_semester()

        if not semester:
            return jsonify({
                "success": True,
                "active": False,
                "semester": None
            }), 200

        today = datetime.now(THAI_TZ).date()

        is_in_period = (
            semester["start_date"]
            <= today
            <= semester["end_date"]
        )

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
        current_app.logger.exception(
            "Unable to retrieve check-in semester"
        )

        return jsonify({
            "success": False,
            "message": "ไม่สามารถดึงข้อมูลภาคเรียนได้"
        }), 500


# =========================================================
# GET: Recent Scan Logs
# =========================================================

@checkin_bp.route("/api/scans/recent", methods=["GET"])
def api_recent_scans():
    try:
        # จำกัดจำนวนรายการสแกนล่าสุด
        limit = request.args.get(
            "limit",
            default=50,
            type=int
        )

        limit = max(1, min(limit, 100))

        # คำนวณสถิติภาคเรียนปัจจุบัน
        statistics = get_attendance_statistics()

        # ดึงรายการสแกนล่าสุด
        response = (
            supabase.table("scan_logs")
            .select("""
                id,
                user_id,
                scanned_at,
                status,
                fingerprint_id,
                subject_id,
                users (
                    student_id,
                    full_name,
                    department
                ),
                subjects (
                    id,
                    code,
                    name
                )
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

            # ค้นหาสถิติของนักศึกษาในรายวิชานี้
            stats = statistics.get(
                (str(user_id), str(subject_id)),
                {
                    "attended_count": 0,
                    "absent_count": 0
                }
            )

            rows.append({
                "id": row.get("id"),
                "scanned_at": row.get("scanned_at"),
                "status": row.get("status"),
                "fingerprint_id": row.get("fingerprint_id"),

                # User information
                "user_id": user_id,
                "student_id": user.get("student_id"),
                "full_name": user.get("full_name"),
                "department": user.get("department"),

                # Subject information
                "subject_id": subject_id,
                "subject_code": subject.get("code"),
                "subject_name": subject.get("name"),

                # Attendance statistics
                "attended_count": stats["attended_count"],
                "absent_count": stats["absent_count"]
            })

        return jsonify(rows), 200

    except Exception:
        current_app.logger.exception(
            "Unable to retrieve recent scans"
        )

        return jsonify({
            "success": False,
            "message": "ไม่สามารถดึงรายการสแกนล่าสุดได้"
        }), 500


# =========================================================
# Helper: Get Attendance Statistics
# =========================================================

def get_attendance_statistics():
    now = datetime.now(THAI_TZ)
    today = now.date()

    # =========================================
    # 1. Get Active Semester
    # =========================================

    semester_range = get_semester_date_range()

    if not semester_range:
        return {}

    semester_start, semester_end = semester_range

    # จำกัดวันสิ้นสุดไม่ให้เกินวันปัจจุบัน
    statistics_end = min(today, semester_end)

    # ยังไม่ถึงวันเริ่มภาคเรียน
    if today < semester_start:
        return {}

    # =========================================
    # 2. Get Subjects
    # =========================================

    subjects_response = (
        supabase.table("subjects")
        .select("id, section_id, class_days, end_time")
        .execute()
    )

    subjects = subjects_response.data or []

    # =========================================
    # 3. Get Users
    # =========================================

    users_response = (
        supabase.table("users")
        .select("id, section_id")
        .execute()
    )

    users = users_response.data or []

    # =========================================
    # 4. Get Scan Logs within Semester
    # =========================================

    start_datetime = datetime.combine(
        semester_start,
        datetime.min.time(),
        tzinfo=THAI_TZ
    )

    end_datetime = datetime.combine(
        statistics_end,
        datetime.max.time(),
        tzinfo=THAI_TZ
    )

    scan_logs = []
    offset = 0
    page_size = 1000

    while True:
        response = (
            supabase.table("scan_logs")
            .select("user_id, subject_id, scanned_at, status")
            .gte(
                "scanned_at",
                start_datetime.isoformat()
            )
            .lte(
                "scanned_at",
                end_datetime.isoformat()
            )
            .order("scanned_at", desc=False)
            .range(offset, offset + page_size - 1)
            .execute()
        )

        batch = response.data or []
        scan_logs.extend(batch)

        if len(batch) < page_size:
            break

        offset += page_size

    # =========================================
    # 5. Collect Attendance Dates
    # =========================================

    attended_dates = {}

    for log in scan_logs:
        if log.get("status") not in ("on_time", "late"):
            continue

        user_id = log.get("user_id")
        subject_id = log.get("subject_id")
        scanned_at = log.get("scanned_at")

        if (
            user_id is None
            or subject_id is None
            or not scanned_at
        ):
            continue

        try:
            scanned_datetime = datetime.fromisoformat(
                str(scanned_at).replace("Z", "+00:00")
            )

            if scanned_datetime.tzinfo is None:
                scanned_datetime = scanned_datetime.replace(
                    tzinfo=THAI_TZ
                )

            scanned_date = scanned_datetime.astimezone(
                THAI_TZ
            ).date()

        except (ValueError, TypeError):
            continue

        key = (
            str(user_id),
            str(subject_id)
        )

        attended_dates.setdefault(key, set()).add(
            scanned_date
        )

    # =========================================
    # 6. Calculate Attendance Statistics
    # =========================================

    statistics = {}

    for subject in subjects:
        subject_id = subject.get("id")
        section_id = subject.get("section_id")

        class_days = normalize_class_days(
            subject.get("class_days")
        )

        end_time = parse_subject_end_time(
            subject.get("end_time")
        )

        if not class_days or not end_time:
            continue

        # หาวันเรียนที่ผ่านเวลาเลิกเรียนแล้ว
        class_dates = set()
        current_date = semester_start

        while current_date <= statistics_end:
            weekday = current_date.strftime("%A")

            if weekday in class_days:
                is_past_class = current_date < today

                if current_date == today:
                    is_past_class = (
                        now.time().replace(tzinfo=None)
                        >= end_time
                    )

                if is_past_class:
                    class_dates.add(current_date)

            current_date += timedelta(days=1)

        # เลือกนักศึกษาที่อยู่ Section เดียวกับวิชา
        section_users = [
            user
            for user in users
            if str(user.get("section_id"))
            == str(section_id)
        ]

        for user in section_users:
            user_id = user.get("id")

            key = (
                str(user_id),
                str(subject_id)
            )

            attended = attended_dates.get(
                key,
                set()
            ).intersection(class_dates)

            attended_count = len(attended)
            absent_count = len(class_dates) - attended_count

            statistics[key] = {
                "attended_count": attended_count,
                "absent_count": absent_count
            }

    return statistics
