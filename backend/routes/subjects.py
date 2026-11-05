
from flask import Blueprint, jsonify, request
from config.database import supabase
from openpyxl import load_workbook
from datetime import datetime, time as datetime_time
from io import BytesIO
import ast

subjects_bp = Blueprint("subjects", __name__)


# =========================================================
# GET: Retrieve Subjects
# =========================================================

@subjects_bp.route("/api/subjects", methods=["GET"])
def get_subjects():
    try:
        response = (
            supabase.table("subjects")
            .select("""
                id,
                code,
                name,
                section_id,
                start_time,
                end_time,
                late_after_minutes,
                class_days,
                created_at
            """)
            .order("id")
            .execute()
        )

        sections_response = (
            supabase.table("sections")
            .select("id, name")
            .execute()
        )

        section_map = {
            str(section["id"]): section["name"]
            for section in (sections_response.data or [])
        }

        subjects = []

        for subject in response.data or []:
            subject["section_name"] = section_map.get(
                str(subject.get("section_id")),
                "-"
            )
            subjects.append(subject)

        return jsonify(subjects), 200

    except Exception:
        subjects_bp.logger.exception(
            "Unable to retrieve subjects"
        )

        return jsonify({
            "success": False,
            "message": "Unable to retrieve subjects"
        }), 500


# =========================================================
# POST: Create Subject
# =========================================================

@subjects_bp.route("/api/subjects", methods=["POST"])
def create_subject():
    payload = request.get_json(silent=True) or {}

    code = str(payload.get("code") or "").strip()
    name = str(payload.get("name") or "").strip()
    section_id_raw = payload.get("section_id")
    class_days = payload.get("class_days")
    start_time = str(payload.get("start_time") or "").strip()
    end_time = str(payload.get("end_time") or "").strip()
    late_after_minutes = payload.get("late_after_minutes", 0)

    if not code or not name:
        return jsonify({
            "success": False,
            "message": "กรุณากรอกรหัสวิชาและชื่อวิชา"
        }), 400

    if section_id_raw in (None, ""):
        return jsonify({
            "success": False,
            "message": "กรุณาเลือก Section"
        }), 400

    try:
        section_id = int(section_id_raw)
        late_after_minutes = int(late_after_minutes)

        if late_after_minutes < 0:
            raise ValueError()

    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Section หรือจำนวนนาทีผ่อนผันไม่ถูกต้อง"
        }), 400

    if not isinstance(class_days, list) or not class_days:
        return jsonify({
            "success": False,
            "message": "กรุณาเลือกวันเรียนอย่างน้อย 1 วัน"
        }), 400

    valid_days = {
        "Monday", "Tuesday", "Wednesday",
        "Thursday", "Friday", "Saturday", "Sunday"
    }

    if not all(day in valid_days for day in class_days):
        return jsonify({
            "success": False,
            "message": "วันเรียนไม่ถูกต้อง"
        }), 400

    try:
        start = datetime_time.fromisoformat(start_time)
        end = datetime_time.fromisoformat(end_time)

        if start >= end:
            return jsonify({
                "success": False,
                "message": "เวลาเลิกเรียนต้องมากกว่าเวลาเริ่มเรียน"
            }), 400

        existing = (
            supabase.table("subjects")
            .select("id")
            .eq("code", code)
            .limit(1)
            .execute()
        )

        if existing.data:
            return jsonify({
                "success": False,
                "message": "รหัสวิชานี้มีอยู่ในระบบแล้ว"
            }), 409

        section = (
            supabase.table("sections")
            .select("id")
            .eq("id", section_id)
            .limit(1)
            .execute()
        )

        if not section.data:
            return jsonify({
                "success": False,
                "message": "ไม่พบ Section ที่เลือก"
            }), 404

        subject_data = {
            "code": code,
            "name": name,
            "section_id": section_id,
            "class_days": class_days,
            "start_time": start_time,
            "end_time": end_time,
            "late_after_minutes": late_after_minutes
        }

        response = (
            supabase.table("subjects")
            .insert(subject_data)
            .execute()
        )

        if not response.data:
            raise Exception("Subject insert returned no data")

        return jsonify({
            "success": True,
            "message": "เพิ่มรายวิชาสำเร็จ",
            "subject": response.data[0]
        }), 201

    except ValueError:
        return jsonify({
            "success": False,
            "message": "รูปแบบเวลาไม่ถูกต้อง"
        }), 400

    except Exception:
        subjects_bp.logger.exception(
            "Unable to create subject"
        )

        return jsonify({
            "success": False,
            "message": "ไม่สามารถเพิ่มรายวิชาได้"
        }), 500

# =========================================================
# PUT: Update Subject
# =========================================================

@subjects_bp.route(
    "/api/subjects/<int:subject_id>",
    methods=["PUT"]
)
def update_subject(subject_id):
    payload = request.get_json(silent=True) or {}

    code = str(payload.get("code") or "").strip()
    name = str(payload.get("name") or "").strip()
    section_id_raw = payload.get("section_id")
    class_days = payload.get("class_days")
    start_time = str(payload.get("start_time") or "").strip()
    end_time = str(payload.get("end_time") or "").strip()
    late_after_minutes = payload.get("late_after_minutes", 0)

    if not code or not name:
        return jsonify({
            "success": False,
            "message": "กรุณากรอกรหัสวิชาและชื่อวิชา"
        }), 400

    if section_id_raw in (None, ""):
        return jsonify({
            "success": False,
            "message": "กรุณาเลือก Section"
        }), 400

    try:
        section_id = int(section_id_raw)
        late_after_minutes = int(late_after_minutes)

        if late_after_minutes < 0:
            raise ValueError()

    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Section หรือจำนวนนาทีผ่อนผันไม่ถูกต้อง"
        }), 400

    valid_days = {
        "Monday", "Tuesday", "Wednesday",
        "Thursday", "Friday", "Saturday", "Sunday"
    }

    if (
        not isinstance(class_days, list)
        or not class_days
        or not all(day in valid_days for day in class_days)
    ):
        return jsonify({
            "success": False,
            "message": "กรุณาเลือกวันเรียนให้ถูกต้อง"
        }), 400

    try:
        start = datetime_time.fromisoformat(start_time)
        end = datetime_time.fromisoformat(end_time)

        if start >= end:
            return jsonify({
                "success": False,
                "message": "เวลาเลิกเรียนต้องมากกว่าเวลาเริ่มเรียน"
            }), 400

        # ตรวจสอบว่ามีรายวิชานี้หรือไม่
        existing = (
            supabase.table("subjects")
            .select("id")
            .eq("id", subject_id)
            .limit(1)
            .execute()
        )

        if not existing.data:
            return jsonify({
                "success": False,
                "message": "ไม่พบรายวิชาที่ต้องการแก้ไข"
            }), 404

        # ตรวจสอบรหัสวิชาซ้ำ โดยไม่รวมรายวิชาปัจจุบัน
        duplicate = (
            supabase.table("subjects")
            .select("id")
            .eq("code", code)
            .neq("id", subject_id)
            .limit(1)
            .execute()
        )

        if duplicate.data:
            return jsonify({
                "success": False,
                "message": "รหัสวิชานี้มีอยู่ในระบบแล้ว"
            }), 409

        # ตรวจสอบ Section
        section = (
            supabase.table("sections")
            .select("id")
            .eq("id", section_id)
            .limit(1)
            .execute()
        )

        if not section.data:
            return jsonify({
                "success": False,
                "message": "ไม่พบ Section ที่เลือก"
            }), 404

        subject_data = {
            "code": code,
            "name": name,
            "section_id": section_id,
            "class_days": class_days,
            "start_time": start_time,
            "end_time": end_time,
            "late_after_minutes": late_after_minutes
        }

        response = (
            supabase.table("subjects")
            .update(subject_data)
            .eq("id", subject_id)
            .execute()
        )

        if not response.data:
            raise Exception("Subject update returned no data")

        return jsonify({
            "success": True,
            "message": "แก้ไขรายวิชาสำเร็จ",
            "subject": response.data[0]
        }), 200

    except ValueError:
        return jsonify({
            "success": False,
            "message": "รูปแบบเวลาไม่ถูกต้อง"
        }), 400

    except Exception:
        from flask import current_app
        current_app.logger.exception(
            "Unable to update subject"
        )

        return jsonify({
            "success": False,
            "message": "ไม่สามารถแก้ไขรายวิชาได้"
        }), 500

# =========================================================
# DELETE: Delete Subject
# =========================================================

@subjects_bp.route(
    "/api/subjects/<int:subject_id>",
    methods=["DELETE"]
)
def delete_subject(subject_id):
    try:
        existing = (
            supabase.table("subjects")
            .select("id")
            .eq("id", subject_id)
            .limit(1)
            .execute()
        )

        if not existing.data:
            return jsonify({
                "success": False,
                "message": "ไม่พบรายวิชาที่ต้องการลบ"
            }), 404

        logs = (
            supabase.table("scan_logs")
            .select("id")
            .eq("subject_id", subject_id)
            .limit(1)
            .execute()
        )
        if logs.data:
            return jsonify({
                "success": False,
                "message": "ไม่สามารถลบรายวิชานี้ได้ เนื่องจากมีประวัติการเช็กชื่อ"
            }), 409

        response = (
            supabase.table("subjects")
            .delete()
            .eq("id", subject_id)
            .execute()
        )

        if not response.data:
            return jsonify({
                "success": False,
                "message": "ไม่สามารถลบรายวิชาได้"
            }), 400

        return jsonify({
            "success": True,
            "message": "ลบรายวิชาสำเร็จ"
        }), 200

    except Exception:
        subjects_bp.logger.exception(
            "Unable to delete subject"
        )

        return jsonify({
            "success": False,
            "message": "ไม่สามารถลบรายวิชาได้"
        }), 500


# =========================================================
# IMPORT HELPERS
# =========================================================

def format_excel_time(value):
    """
    Convert Excel time into HH:MM:SS
    """

    if isinstance(value, datetime_time):
        return value.strftime("%H:%M:%S")

    if isinstance(value, datetime):
        return value.strftime("%H:%M:%S")

    if value is None or str(value).strip() == "":
        raise ValueError("กรุณาระบุเวลาเรียน")

    value = str(value).strip()

    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(
                value,
                fmt
            ).strftime("%H:%M:%S")

        except ValueError:
            continue

    raise ValueError(
        f"รูปแบบเวลาไม่ถูกต้อง: {value}"
    )


def parse_class_days(value):
    """
    Convert Excel class_days into a list.

    Supported examples:
    Monday,Wednesday
    Monday;Wednesday
    ['Monday', 'Wednesday']
    """

    valid_days = {
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday"
    }

    if isinstance(value, (list, tuple)):
        days = list(value)

    else:
        text = str(value or "").strip()

        if not text:
            raise ValueError("กรุณาระบุวันเรียน")

        try:
            parsed = ast.literal_eval(text)

            if isinstance(parsed, (list, tuple)):
                days = list(parsed)
            else:
                days = text.replace(";", ",").replace(
                    "|", ","
                ).split(",")

        except (ValueError, SyntaxError):
            days = text.replace(
                ";", ","
            ).replace(
                "|", ","
            ).split(",")

    days = list(dict.fromkeys(
        str(day).strip().capitalize()
        for day in days
        if str(day).strip()
    ))

    if not days:
        raise ValueError("กรุณาระบุวันเรียน")

    invalid_days = [
        day for day in days
        if day not in valid_days
    ]

    if invalid_days:
        raise ValueError(
            "วันเรียนไม่ถูกต้อง: " + ", ".join(invalid_days)
        )

    return days


# =========================================================
# POST: Import Subjects from Excel
# =========================================================

@subjects_bp.route(
    "/api/subjects/import",
    methods=["POST"]
)
def import_subjects_excel():
    file = request.files.get("subject_file")

    if not file or not file.filename:
        return jsonify({
            "success": False,
            "message": "กรุณาเลือกไฟล์ Excel"
        }), 400

    if not file.filename.lower().endswith(".xlsx"):
        return jsonify({
            "success": False,
            "message": "รองรับเฉพาะไฟล์ .xlsx"
        }), 400

    workbook = None

    try:
        workbook = load_workbook(
            BytesIO(file.read()),
            read_only=True,
            data_only=True
        )

        sheet = workbook.active

        header_values = next(
            sheet.iter_rows(
                min_row=1,
                max_row=1,
                values_only=True
            ),
            None
        )

        if not header_values:
            raise ValueError(
                "ไฟล์ Excel ไม่มีหัวคอลัมน์"
            )

        headers = [
            str(value or "").strip().lower()
            for value in header_values
        ]

        # ใช้ section ตาม Excel Template จริง
        required = [
            "code",
            "name",
            "section",
            "class_days",
            "start_time",
            "end_time",
            "late_after_minutes"
        ]

        missing = [
            column
            for column in required
            if column not in headers
        ]

        if missing:
            raise ValueError(
                "ไม่พบคอลัมน์: " + ", ".join(missing)
            )

        # โหลด Section ทั้ง ID และชื่อ
        section_response = (
            supabase.table("sections")
            .select("id, name")
            .execute()
        )

        section_map = {
            str(section["name"]).strip().casefold(): section["id"]
            for section in (section_response.data or [])
            if section.get("name")
        }

        # โหลดรหัสวิชาที่มีอยู่แล้ว
        existing_response = (
            supabase.table("subjects")
            .select("code")
            .execute()
        )

        existing_codes = {
            str(subject["code"]).strip().casefold()
            for subject in (existing_response.data or [])
            if subject.get("code")
        }

        payloads = []
        errors = []
        seen_codes = set()

        # อ่านข้อมูล Excel
        for row_number, values in enumerate(
            sheet.iter_rows(
                min_row=2,
                values_only=True
            ),
            start=2
        ):
            row = dict(zip(headers, values))

            if not any(value is not None for value in values):
                continue

            try:
                code = str(
                    row.get("code") or ""
                ).strip()

                name = str(
                    row.get("name") or ""
                ).strip()

                if not code or not name:
                    raise ValueError(
                        "ต้องระบุ code และ name"
                    )

                # ตรวจสอบรหัสวิชาซ้ำ
                normalized_code = code.casefold()

                if normalized_code in existing_codes:
                    raise ValueError(
                        f"รหัสวิชา {code} มีอยู่ในระบบแล้ว"
                    )

                if normalized_code in seen_codes:
                    raise ValueError(
                        f"รหัสวิชา {code} ซ้ำในไฟล์"
                    )

                # แปลงชื่อ Section เป็น section_id
                section_name = str(
                    row.get("section") or ""
                ).strip()

                if not section_name:
                    raise ValueError(
                        "กรุณาระบุ Section"
                    )

                section_id = section_map.get(
                    section_name.casefold()
                )

                if section_id is None:
                    raise ValueError(
                        f"ไม่พบ Section: {section_name}"
                    )

                # ตรวจสอบวันเรียน
                class_days = parse_class_days(
                    row.get("class_days")
                )

                # ตรวจสอบเวลา
                start_time = format_excel_time(
                    row.get("start_time")
                )

                end_time = format_excel_time(
                    row.get("end_time")
                )

                start = datetime.strptime(
                    start_time,
                    "%H:%M:%S"
                ).time()

                end = datetime.strptime(
                    end_time,
                    "%H:%M:%S"
                ).time()

                if start >= end:
                    raise ValueError(
                        "เวลาเลิกเรียนต้องมากกว่าเวลาเริ่มเรียน"
                    )

                # ตรวจสอบนาทีผ่อนผัน
                late_value = row.get(
                    "late_after_minutes"
                )

                if late_value in (None, ""):
                    late_minutes = 0

                else:
                    if isinstance(late_value, bool):
                        raise ValueError(
                            "late_after_minutes ต้องเป็นตัวเลข"
                        )

                    late_minutes = int(late_value)

                    if float(late_value) != late_minutes:
                        raise ValueError(
                            "late_after_minutes ต้องเป็นจำนวนเต็ม"
                        )

                if late_minutes < 0:
                    raise ValueError(
                        "late_after_minutes ต้องเป็น 0 ขึ้นไป"
                    )

                # เตรียมข้อมูลสำหรับ Insert
                payloads.append({
                    "code": code,
                    "name": name,
                    "section_id": section_id,
                    "class_days": class_days,
                    "start_time": start_time,
                    "end_time": end_time,
                    "late_after_minutes": late_minutes
                })

                seen_codes.add(normalized_code)

            except (ValueError, TypeError, OverflowError) as exc:
                errors.append({
                    "row": row_number,
                    "message": str(exc)
                })

        # หากพบข้อมูลผิดพลาด จะไม่ Insert ข้อมูลใด ๆ
        if errors:
            return jsonify({
                "success": False,
                "message": "พบข้อมูลผิดพลาด กรุณาตรวจสอบไฟล์ Excel",
                "errors": errors[:50],
                "total_errors": len(errors)
            }), 400

        if not payloads:
            return jsonify({
                "success": False,
                "message": "ไม่พบข้อมูลรายวิชาสำหรับนำเข้า"
            }), 400

        # Insert แบบ Batch ครั้งละ 100 รายการ
        imported = 0

        for start in range(0, len(payloads), 100):
            batch = payloads[start:start + 100]

            response = (
                supabase.table("subjects")
                .insert(batch)
                .execute()
            )

            imported += len(response.data or [])

        return jsonify({
            "success": True,
            "message": "Import รายวิชาสำเร็จ",
            "result": {
                "inserted": imported,
                "errors": []
            }
        }), 200

    except ValueError as exc:
        return jsonify({
            "success": False,
            "message": str(exc)
        }), 400

    except Exception:
        subjects_bp.logger.exception(
            "Unable to import subjects"
        )

        return jsonify({
            "success": False,
            "message": "ไม่สามารถ Import รายวิชาได้"
        }), 500

    finally:
        if workbook is not None:
            workbook.close()
