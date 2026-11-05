
from flask import Blueprint, jsonify
from config.database import supabase
from flask import Blueprint, jsonify, request
from datetime import datetime, timezone, timedelta
from config.database import supabase
from openpyxl import load_workbook

users_bp = Blueprint("users", __name__)


@users_bp.route("/api/users", methods=["GET"])
def get_users():
    try:
        response = (
            supabase.table("users")
            .select("""
                id,
                student_id,
                full_name,
                department,
                fingerprint_id,
                section_id,
                created_at
            """)
            .order("student_id", desc=False)
            .execute()
        )

        sections_response = (
            supabase.table("sections")
            .select("id, name")
            .order("name")
            .execute()
        )

        sections = sections_response.data or []

        section_map = {
            str(section["id"]): section["name"]
            for section in sections
        }

        users = []

        for user in response.data or []:
            user["section_name"] = section_map.get(
                str(user.get("section_id")),
                "-"
            )
            users.append(user)

        return jsonify(users), 200

    except Exception:
        users_bp.logger.exception("Unable to retrieve users")
        return jsonify({
            "success": False,
            "message": "Unable to retrieve users"
        }), 500


@users_bp.route("/api/sections", methods=["GET"])
def get_sections():
    try:
        response = (
            supabase.table("sections")
            .select("id, name")
            .order("name")
            .execute()
        )

        return jsonify(response.data or []), 200

    except Exception:
        users_bp.logger.exception("Unable to retrieve sections")
        return jsonify({
            "success": False,
            "message": "Unable to retrieve sections"
        }), 500


@users_bp.route("/api/users", methods=["POST"])
def create_user():
    payload = request.get_json(silent=True) or {}

    student_id = str(payload.get("student_id") or "").strip()
    full_name = str(payload.get("full_name") or "").strip()
    department = str(payload.get("department") or "").strip()
    fingerprint_id_raw = payload.get("fingerprint_id")
    fingerprint_id = (
        str(fingerprint_id_raw).strip()
        if fingerprint_id_raw not in (None, "")
        else None
    )
    section_id_raw = payload.get("section_id")

    # ข้อมูลพื้นฐานต้องครบ ส่วน fingerprint_id ยังเว้นว่างได้
    if not student_id or not full_name:
        return jsonify({
            "success": False,
            "message": "กรุณากรอกรหัสนักศึกษาและชื่อ-นามสกุล"
        }), 400

    if fingerprint_id is not None and not fingerprint_id.isdigit():
        return jsonify({
            "success": False,
            "message": "รหัสลายนิ้วมือต้องเป็นตัวเลข"
        }), 400

    try:
        # Check duplicate student ID
        existing_student = (
            supabase.table("users")
            .select("id")
            .eq("student_id", student_id)
            .limit(1)
            .execute()
        )

        if existing_student.data:
            return jsonify({
                "success": False,
                "message": "รหัสนักศึกษานี้มีอยู่ในระบบแล้ว"
            }), 409

        # Check duplicate fingerprint ID
        if fingerprint_id:
            existing_fingerprint = (
                supabase.table("users")
                .select("id")
                .eq("fingerprint_id", fingerprint_id)
                .limit(1)
                .execute()
            )

            if existing_fingerprint.data:
                return jsonify({
                    "success": False,
                    "message": "รหัสลายนิ้วมือนี้มีผู้ใช้งานแล้ว"
                }), 409

        # Validate Section
        section_id = None

        if section_id_raw not in (None, ""):
            try:
                section_id = int(section_id_raw)
            except (ValueError, TypeError):
                return jsonify({
                    "success": False,
                    "message": "Section ไม่ถูกต้อง"
                }), 400

            section_response = (
                supabase.table("sections")
                .select("id")
                .eq("id", section_id)
                .limit(1)
                .execute()
            )

            if not section_response.data:
                return jsonify({
                    "success": False,
                    "message": "ไม่พบ Section ที่เลือก"
                }), 404

        # Thailand timestamp
        created_at = datetime.now(
            timezone(timedelta(hours=7))
        ).isoformat(timespec="seconds")

        user_data = {
            "student_id": student_id,
            "full_name": full_name,
            "department": department or None,
            "fingerprint_id": fingerprint_id,
            "created_at": created_at
        }

        if section_id is not None:
            user_data["section_id"] = section_id

        # Insert user
        response = (
            supabase.table("users")
            .insert(user_data)
            .execute()
        )

        if not response.data:
            raise Exception("User insert returned no data")

        user = response.data[0]

        # Return only public fields
        return jsonify({
            "success": True,
            "message": "เพิ่มผู้ใช้สำเร็จ",
            "user": {
                "id": user.get("id"),
                "student_id": user.get("student_id"),
                "full_name": user.get("full_name"),
                "department": user.get("department"),
                "fingerprint_id": user.get("fingerprint_id"),
                "section_id": user.get("section_id"),
                "created_at": user.get("created_at")
            }
        }), 201

    except Exception:
        users_bp.logger.exception("Unable to create user")

        return jsonify({
            "success": False,
            "message": "ไม่สามารถเพิ่มผู้ใช้ได้"
        }), 500

@users_bp.route("/api/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    try:
        existing = (
            supabase.table("users")
            .select("id")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        if not existing.data:
            return jsonify({"success": False, "message": "ไม่พบผู้ใช้ที่ต้องการลบ"}), 404

        # เก็บประวัติการเช็กชื่อไว้เสมอ ไม่อนุญาตลบผู้ใช้ที่มีประวัติ
        logs = (
            supabase.table("scan_logs")
            .select("id")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if logs.data:
            return jsonify({
                "success": False,
                "message": "ไม่สามารถลบผู้ใช้นี้ได้ เนื่องจากมีประวัติการเช็กชื่อ"
            }), 409

        response = (
            supabase.table("users")
            .delete()
            .eq("id", user_id)
            .execute()
        )
        if not response.data:
            return jsonify({"success": False, "message": "ไม่สามารถลบผู้ใช้ได้"}), 400

        return jsonify({"success": True, "message": "ลบผู้ใช้สำเร็จ"}), 200
    except Exception:
        users_bp.logger.exception("Unable to delete user")
        return jsonify({"success": False, "message": "ไม่สามารถลบผู้ใช้ได้"}), 500


@users_bp.route("/api/sections", methods=["POST"])
def create_section():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name") or "").strip()

    if not name:
        return jsonify({
            "success": False,
            "message": "กรุณากรอกชื่อ Section"
        }), 400

    try:
        # ตรวจสอบชื่อ Section ซ้ำ
        existing = (
            supabase.table("sections")
            .select("id")
            .ilike("name", name)
            .limit(1)
            .execute()
        )

        if existing.data:
            return jsonify({
                "success": False,
                "message": "ชื่อ Section นี้มีอยู่ในระบบแล้ว"
            }), 409

        response = (
            supabase.table("sections")
            .insert({"name": name})
            .execute()
        )

        if not response.data:
            raise Exception("Section insert returned no data")

        return jsonify({
            "success": True,
            "message": "เพิ่ม Section สำเร็จ",
            "section": response.data[0]
        }), 201

    except Exception:
        users_bp.logger.exception("Unable to create section")
        return jsonify({
            "success": False,
            "message": "ไม่สามารถเพิ่ม Section ได้"
        }), 500


@users_bp.route("/api/sections/<int:section_id>", methods=["DELETE"])
def delete_section(section_id):
    try:
        # ตรวจสอบว่ามีผู้ใช้งานอยู่ใน Section นี้หรือไม่
        users = (
            supabase.table("users")
            .select("id")
            .eq("section_id", section_id)
            .limit(1)
            .execute()
        )

        if users.data:
            return jsonify({
                "success": False,
                "message": "ไม่สามารถลบ Section ได้ เนื่องจากมีผู้ใช้งานอยู่"
            }), 409

        subjects = (
            supabase.table("subjects")
            .select("id")
            .eq("section_id", section_id)
            .limit(1)
            .execute()
        )
        if subjects.data:
            return jsonify({
                "success": False,
                "message": "ไม่สามารถลบ Section ได้ เนื่องจากมีรายวิชาใช้งานอยู่"
            }), 409

        response = (
            supabase.table("sections")
            .delete()
            .eq("id", section_id)
            .execute()
        )

        if not response.data:
            return jsonify({
                "success": False,
                "message": "ไม่พบ Section ที่ต้องการลบ"
            }), 404

        return jsonify({
            "success": True,
            "message": "ลบ Section สำเร็จ"
        }), 200

    except Exception:
        users_bp.logger.exception("Unable to delete section")
        return jsonify({
            "success": False,
            "message": "ไม่สามารถลบ Section ได้"
        }), 500


@users_bp.route("/api/users/import", methods=["POST"])
def import_users_excel():
    file = request.files.get("excel_file")

    if not file or not file.filename:
        return jsonify({
            "success": False,
            "message": "กรุณาเลือกไฟล์ Excel"
        }), 400

    if not file.filename.lower().endswith((".xlsx", ".xlsm")):
        return jsonify({
            "success": False,
            "message": "รองรับเฉพาะไฟล์ .xlsx และ .xlsm"
        }), 400

    workbook = None

    try:
        workbook = load_workbook(
            file,
            read_only=True,
            data_only=True
        )

        sheet = workbook.active

        header_values = next(
            sheet.iter_rows(min_row=1, max_row=1, values_only=True),
            None
        )

        if not header_values:
            raise ValueError("ไฟล์ Excel ไม่มีหัวคอลัมน์")

        headers = [
            str(value or "").strip().lower()
            for value in header_values
        ]

        required = ["student_id", "full_name"]

        missing = [column for column in required if column not in headers]

        if missing:
            raise ValueError(
                "ไม่พบคอลัมน์: " + ", ".join(missing)
            )

        section_response = (
            supabase.table("sections")
            .select("id, name")
            .execute()
        )

        section_map = {
            str(item["name"]).strip().casefold(): int(item["id"])
            for item in (section_response.data or [])
            if item.get("name") and item.get("id") is not None
        }

        valid_section_ids = {
            str(item["id"])
            for item in (section_response.data or [])
        }

        result = {
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "errors": []
        }

        seen_student_ids = set()

        for row_number, values in enumerate(
            sheet.iter_rows(min_row=2, values_only=True),
            start=2
        ):
            row = dict(zip(headers, values))

            if not any(value is not None for value in values):
                continue

            raw_student_id = row.get("student_id")
            student_id = str(raw_student_id or "").strip()

            if student_id.endswith(".0"):
                student_id = student_id[:-2]

            full_name = str(row.get("full_name") or "").strip()
            department = str(row.get("department") or "").strip() or None

            if not student_id or not full_name:
                result["skipped"] += 1
                result["errors"].append({
                    "row": row_number,
                    "message": "กรุณาระบุ student_id และ full_name"
                })
                continue

            if not student_id.isdigit():
                result["skipped"] += 1
                result["errors"].append({
                    "row": row_number,
                    "message": "student_id ต้องเป็นตัวเลข"
                })
                continue

            if student_id in seen_student_ids:
                result["skipped"] += 1
                result["errors"].append({
                    "row": row_number,
                    "message": f"student_id {student_id} ซ้ำในไฟล์"
                })
                continue

            seen_student_ids.add(student_id)

            # Resolve Section by ID or name
            section_id = None
            raw_section_id = row.get("section_id")
            raw_section_name = str(row.get("section") or "").strip()

            if raw_section_id not in (None, ""):
                section_text = str(raw_section_id).strip()

                if section_text.endswith(".0"):
                    section_text = section_text[:-2]

                if section_text not in valid_section_ids:
                    result["skipped"] += 1
                    result["errors"].append({
                        "row": row_number,
                        "message": f"ไม่พบ Section ID: {section_text}"
                    })
                    continue

                section_id = int(section_text)

            elif raw_section_name:
                normalized_name = raw_section_name.casefold()

                if normalized_name.startswith("section "):
                    normalized_name = normalized_name[len("section "):].strip()

                matched_id = section_map.get(normalized_name)

                # รองรับชื่อ Section แบบเต็ม เช่น Section 1
                if matched_id is None:
                    matched_id = section_map.get(raw_section_name.casefold())

                if matched_id is None:
                    result["skipped"] += 1
                    result["errors"].append({
                        "row": row_number,
                        "message": f"ไม่พบ Section: {raw_section_name}"
                    })
                    continue

                section_id = matched_id

            try:
                existing = (
                    supabase.table("users")
                    .select("id")
                    .eq("student_id", student_id)
                    .limit(1)
                    .execute()
                )

                if existing.data:
                    update_data = {
                        "full_name": full_name,
                        "department": department
                    }

                    if section_id is not None:
                        update_data["section_id"] = section_id

                    supabase.table("users").update(
                        update_data
                    ).eq(
                        "id", existing.data[0]["id"]
                    ).execute()

                    result["updated"] += 1
                    continue

                # Import เฉพาะข้อมูลพื้นฐาน ไม่กำหนด fingerprint_id จาก student_id
                from datetime import datetime, timezone, timedelta

                user_data = {
                    "student_id": student_id,
                    "full_name": full_name,
                    "department": department,
                    "created_at": datetime.now(
                        timezone(timedelta(hours=7))
                    ).isoformat(timespec="seconds")
                }

                if section_id is not None:
                    user_data["section_id"] = section_id

                supabase.table("users").insert(user_data).execute()

                result["inserted"] += 1

            except Exception as exc:
                users_bp.logger.exception(
                    "Import user row %s failed", row_number
                )

                result["skipped"] += 1
                result["errors"].append({
                    "row": row_number,
                    "message": str(exc)
                })

        return jsonify({
            "success": True,
            "message": "Import ผู้ใช้เสร็จสิ้น",
            "result": result
        }), 200

    except ValueError as exc:
        return jsonify({
            "success": False,
            "message": str(exc)
        }), 400

    except Exception:
        users_bp.logger.exception("Unable to import users")
        return jsonify({
            "success": False,
            "message": "ไม่สามารถ Import ผู้ใช้ได้"
        }), 500

    finally:
        if workbook is not None:
            workbook.close()
