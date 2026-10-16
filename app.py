"""
app.py
------
เว็บแอปหลักของระบบเช็คชื่อด้วยลายนิ้วมือ (Flask)

หน้าเว็บ:
  /              แดชบอร์ด - ดูรายการสแกนล่าสุดแบบเรียลไทม์
  /users         จัดการผู้ใช้งาน
  /reports       รายงาน + ดาวน์โหลด Excel

API:
  POST /api/scan
  GET  /api/scans/recent
  GET  /reports/export

Run:
  uvicorn app:asgi_app --host 0.0.0.0 --port 5000 --reload
"""
from openpyxl import load_workbook
import threading
import queue
import base64
import time
from pyzkfp import ZKFP2
import uuid
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file,
    redirect,
    url_for,
    flash,
)

from asgiref.wsgi import WsgiToAsgi

import io

import database as db
from report import build_excel_report
from datetime import datetime, date, timedelta, timezone

THAI_TZ = timezone(timedelta(hours=7))


# =========================================================
# Flask App
# =========================================================

app = Flask(__name__)

app.secret_key = "change-this-secret-key"

@app.template_filter("datetime_format_th")
def datetime_format_th(value):
    if not value:
        return "-"

    try:
        if isinstance(value, str):
            value = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )

        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)

        value = value.astimezone(
            timezone(timedelta(hours=7))
        )

        return value.strftime("%d/%m/%Y : %H:%M")

    except (ValueError, TypeError):
        return str(value)


@app.template_filter("datetime_format")
def datetime_format(value):
    if not value:
        return "-"

    try:
        if isinstance(value, str):
            value = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )

        return value.strftime("%d/%m/%Y : %H:%M")

    except (ValueError, TypeError):
        return str(value)

def delete_fingerprint_template(fingerprint_id):
    """ล้าง Template ใน Supabase (ไม่ใช้ fingerprint_templates.json)"""
    try:
        db.supabase.table("users").update(
            {"fingerprint_template": None}
        ).eq("fingerprint_id", str(fingerprint_id)).execute()
        print(f"[SCANNER] ล้าง Template รหัส {fingerprint_id} จาก Supabase แล้ว")
    except Exception as exc:
        print(f"[SCANNER] ล้าง Template ใน Supabase ไม่สำเร็จ: {exc}")
        raise



# =========================================================
# Supabase
# =========================================================

db.init_db()

scanner_queue = queue.Queue()
scanner_status = {
    "ready": False,
    "error": None
}

scanner_lock = threading.Lock()

enrollment_jobs = {}
enrollment_lock = threading.Lock()


active_subject_id = None
active_subject_lock = threading.Lock()
# =========================================================
# Dashboard
# =========================================================

@app.route("/")
def dashboard():
    logs = db.get_recent_logs(limit=50)
    subjects = _master_list("subjects", "name")

    with active_subject_lock:
        selected_subject_id = active_subject_id

    return render_template(
        "index.html",
        logs=logs,
        subjects=subjects,
        selected_subject_id=selected_subject_id,
    )


@app.route("/attendance/subject", methods=["POST"])
def set_active_subject():
    """กำหนดรายวิชาที่กำลังเช็กชื่อ"""
    global active_subject_id
    subject_id_raw = (request.form.get("subject_id") or "").strip()

    if not subject_id_raw:
        with active_subject_lock:
            active_subject_id = None
        print("[SUBJECT DEBUG] ยกเลิกรายวิชาแล้ว: active_subject_id=None")
        flash("ยกเลิกรายวิชาที่กำลังเช็กชื่อแล้ว", "success")
        return redirect(url_for("dashboard"))

    try:
        subject_id = int(subject_id_raw)
        response = (
            db.supabase.table("subjects")
            .select("id, name")
            .eq("id", subject_id)
            .limit(1)
            .execute()
        )
        subject = (response.data or [None])[0]

        if not subject:
            flash("ไม่พบรายวิชาที่เลือก", "error")
        else:
            with active_subject_lock:
                active_subject_id = subject_id
            print(
                f"[SUBJECT DEBUG] เริ่มเช็กชื่อ: "
                f"active_subject_id={active_subject_id}, "
                f"name={subject.get('name')}"
            )
            flash(f"เริ่มเช็กชื่อรายวิชา {subject.get('name')}", "success")
    except (TypeError, ValueError):
        flash("รหัสรายวิชาไม่ถูกต้อง", "error")
    except Exception as exc:
        flash(f"กำหนดรายวิชาที่เช็กชื่อไม่สำเร็จ: {exc}", "error")

    return redirect(url_for("dashboard"))


@app.route("/api/scans/recent")
def api_recent_scans():
    logs = db.get_recent_logs(limit=50)

    return jsonify([
        dict(row)
        for row in logs
    ])


# =========================================================
# API Scan
# =========================================================


@app.route("/api/scan", methods=["POST"])
def api_scan():
    payload = request.get_json(silent=True) or {}

    fingerprint_id = str(
        payload.get("fingerprint_id") or ""
    ).strip()

    scanned_at = payload.get("scanned_at") or datetime.now(
        THAI_TZ
    ).isoformat(timespec="seconds")

    if not fingerprint_id:
        return jsonify({
            "error": "ต้องระบุ fingerprint_id"
        }), 400

    # ค้นหาผู้ใช้จาก fingerprint_id
    user = db.get_user_by_fingerprint(fingerprint_id)

    # อ่านรายวิชาที่กำลังเช็กชื่อ
    with active_subject_lock:
        subject_id = active_subject_id

    print(
        f"[SCAN DEBUG] fingerprint_id={fingerprint_id}, "
        f"subject_id={subject_id}, "
        f"scanned_at={scanned_at}"
    )

    # กรณีพบผู้ใช้
    if user:
        attendance_status = None

        if subject_id is not None:
            attendance_status = get_attendance_status(
                subject_id,
                scanned_at
            )

        print(
            f"[ATTENDANCE DEBUG] "
            f"student_id={user.get('student_id')}, "
            f"attendance_status={attendance_status}"
        )

        # สถานะการเข้าเรียน
        # on_time = ตรงเวลา
        # late = มาสาย
        # matched = พบผู้ใช้ แต่ยังไม่มีสถานะเข้าเรียน
        log_status = attendance_status or "matched"

        db.add_scan_log(
            fingerprint_id,
            user["id"],
            log_status,
            scanned_at,
            subject_id=subject_id,
        )

        return jsonify({
            "status": log_status,
            "attendance_status": attendance_status,
            "student_id": user.get("student_id"),
            "full_name": user.get("full_name"),
            "department": user.get("department"),
            "subject_id": subject_id,
            "scanned_at": scanned_at,
        }), 200

    # กรณีไม่พบผู้ใช้
    db.add_scan_log(
        fingerprint_id,
        None,
        "unmatched",
        scanned_at,
        subject_id=subject_id,
    )

    return jsonify({
        "status": "unmatched",
        "attendance_status": None,
        "subject_id": subject_id,
        "fingerprint_id": fingerprint_id,
        "scanned_at": scanned_at,
    }), 200

# Users
# =========================================================

@app.route("/users")
def users_page():
    users = db.get_all_users()
    sections = _master_list("sections", "name")

    # แสดงชื่อ Section จาก Master โดยไม่ต้องเก็บชื่อซ้ำใน users
    for user in users:
        section_id = user.get("section_id")
        section = next(
            (item for item in sections if str(item.get("id")) == str(section_id)),
            None,
        )
        user["section_name"] = section.get("name") if section else "-"

    return render_template(
        "users.html",
        users=users,
        sections=sections,
    )


@app.route("/users/add", methods=["POST"])
def users_add():

    student_id = request.form.get(
        "student_id",
        ""
    ).strip()

    full_name = request.form.get(
        "full_name",
        ""
    ).strip()

    department = request.form.get(
        "department",
        ""
    ).strip()

    fingerprint_id = request.form.get(
        "fingerprint_id",
        ""
    ).strip()

    section_id_raw = (request.form.get("section_id") or "").strip()
    # รองรับฟอร์มเดิมที่ยังส่งชื่อ Section มา
    section_name = (request.form.get("section") or "").strip()
    section_id = None

    if section_id_raw:
        try:
            section_id = int(section_id_raw)
        except ValueError:
            flash("Section ไม่ถูกต้อง", "error")
            return redirect(url_for("users_page"))
    elif section_name:
        response = db.supabase.table("sections").select("id,name").execute()
        matched = next(
            (item for item in (response.data or [])
             if item.get("name", "").strip().casefold() == section_name.casefold()),
            None,
        )
        if not matched:
            flash(f"ไม่พบ Section '{section_name}' ใน Master Section", "error")
            return redirect(url_for("users_page"))
        section_id = int(matched["id"])

    # -----------------------------------------------------
    # Validate
    # -----------------------------------------------------

    if not (
        student_id
        and full_name
        and fingerprint_id
    ):

        flash(
            "กรุณากรอกรหัส, ชื่อ-นามสกุล "
            "และรหัสลายนิ้วมือให้ครบ",
            "error",
        )

        return redirect(
            url_for("users_page")
        )

    # -----------------------------------------------------
    # Add User
    # -----------------------------------------------------

    try:

        created_at = datetime.now(
            timezone(timedelta(hours=7))
        ).isoformat(timespec="seconds")

        db.add_user(
            student_id,
            full_name,
            department,
            fingerprint_id,
            created_at=created_at,
            section_id=section_id,
        )

        flash(
            f"เพิ่มผู้ใช้ {full_name} สำเร็จ",
            "success",
        )

    except Exception as exc:
        print(f"[ERROR] เพิ่มผู้ใช้ไม่สำเร็จ: {exc}")

        flash(
            f"เพิ่มผู้ใช้ไม่สำเร็จ: "
            f"รหัสนักศึกษาหรือรหัสลายนิ้วมือซ้ำ ({exc})",
            "error",
        )
    return redirect(
        url_for("users_page")
    )


@app.route("/users/import-excel", methods=["POST"])
def users_import_excel():
    file = request.files.get("excel_file")

    if not file or not file.filename:
        flash("กรุณาเลือกไฟล์ Excel", "error")
        return redirect(url_for("users_page"))

    if not file.filename.lower().endswith((".xlsx", ".xlsm")):
        flash("รองรับไฟล์ .xlsx หรือ .xlsm เท่านั้น", "error")
        return redirect(url_for("users_page"))

    try:
        workbook = load_workbook(
            file,
            read_only=True,
            data_only=True
        )
        sheet = workbook.active

        # อ่านชื่อคอลัมน์จากแถวแรก
        headers = [
            str(cell.value or "").strip().lower()
            for cell in next(sheet.iter_rows())
        ]

        required = ["student_id", "full_name", "department"]
        missing = [name for name in required if name not in headers]

        if missing:
            flash(
                "ไม่พบคอลัมน์: " + ", ".join(missing),
                "error"
            )
            workbook.close()
            return redirect(url_for("users_page"))

        # โหลด Master Section ครั้งเดียว แล้วจับคู่ชื่อจาก Excel เป็น section_id
        section_response = db.supabase.table("sections").select("id,name").execute()
        section_map = {
            str(item.get("name", "")).strip().casefold(): int(item["id"])
            for item in (section_response.data or [])
            if item.get("name") and item.get("id") is not None
        }

        rows = []
        row_errors = []

        for excel_row_number, values in enumerate(
            sheet.iter_rows(min_row=2, values_only=True), start=2
        ):
            row = dict(zip(headers, values))

            student_id = str(row.get("student_id") or "").strip()
            full_name = str(row.get("full_name") or "").strip()
            department = str(row.get("department") or "").strip()
            section_name = str(row.get("section") or "").strip()

            if not student_id and not full_name and not department and not section_name:
                continue

            section_id = None
            if section_name:
                section_id = section_map.get(section_name.casefold())
                if section_id is None:
                    row_errors.append({
                        "row": excel_row_number,
                        "message": f"ไม่พบ Section '{section_name}' ใน Master Section",
                    })
                    continue

            rows.append({
                "student_id": student_id,
                "full_name": full_name,
                "department": department,
                "section_id": section_id,
            })

        workbook.close()

        result = db.import_users_from_excel(rows)
        result.setdefault("errors", [])
        result["errors"] = row_errors + result["errors"]

        flash(
            f"เพิ่มใหม่ {result['inserted']} คน, "
            f"อัปเดตข้อมูลเดิม {result.get('updated', 0)} คน, "
            f"ข้าม {result['skipped']} คน, "
            f"ผิดพลาด {len(result['errors'])} รายการ",
            "success" if not result["errors"] else "error"
        )

        for error in result["errors"][:10]:
            print(
                f"[IMPORT EXCEL] แถว {error['row']}: "
                f"{error['message']}"
            )

    except Exception as exc:
        print(f"[IMPORT EXCEL ERROR] {exc}")
        flash(f"นำเข้า Excel ไม่สำเร็จ: {exc}", "error")

    return redirect(url_for("users_page"))



@app.route("/users/delete/<int:user_id>", methods=["POST"])
def users_delete(user_id):
    try:
        # ค้นหาผู้ใช้ก่อนลบ
        users = db.get_all_users()
        user = next(
            (u for u in users if int(u["id"]) == user_id),
            None,
        )

        if not user:
            flash("ไม่พบผู้ใช้ที่ต้องการลบ", "error")
            return redirect(url_for("users_page"))

        fingerprint_id = user.get("fingerprint_id")

        # ลบผู้ใช้จาก Supabase ก่อน
        db.delete_user(user_id)

        # เมื่อลบผู้ใช้สำเร็จ จึงลบ Template จาก JSON
        if fingerprint_id:
            delete_fingerprint_template(fingerprint_id)

        flash("ลบผู้ใช้และ Template เรียบร้อยแล้ว", "success")

    except Exception as exc:
        print(f"[ERROR] ลบผู้ใช้ไม่สำเร็จ: {exc}")
        flash(f"ลบผู้ใช้ไม่สำเร็จ: {exc}", "error")

    return redirect(url_for("users_page"))

# =========================================================
# Reports
# =========================================================



# =========================================================
# Master Data: Sections and Subjects
# =========================================================

def _master_list(table, order_column):
    response = db.supabase.table(table).select("*").order(order_column).execute()
    return response.data or []

@app.route("/masters/sections", methods=["GET", "POST"])
def sections_page():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("กรุณากรอกชื่อ Section", "error")
        else:
            try:
                db.supabase.table("sections").insert({"name": name}).execute()
                flash("เพิ่ม Section สำเร็จ", "success")
            except Exception as exc:
                flash(f"เพิ่ม Section ไม่สำเร็จ: {exc}", "error")
        return redirect(url_for("sections_page"))
    try:
        sections = _master_list("sections", "name")
    except Exception as exc:
        sections = []
        flash("อ่านตาราง sections ไม่สำเร็จ กรุณารัน SQL สำหรับ Master Data ก่อน: " + str(exc), "error")
    return render_template("sections.html", sections=sections)

@app.route("/masters/sections/<int:section_id>/delete", methods=["POST"])
def sections_delete(section_id):
    try:
        db.supabase.table("sections").delete().eq("id", section_id).execute()
        flash("ลบ Section สำเร็จ", "success")
    except Exception as exc:
        flash(f"ลบ Section ไม่สำเร็จ: {exc}", "error")
    return redirect(url_for("sections_page"))

@app.route("/masters/subjects", methods=["GET", "POST"])
def subjects_page():
    if request.method == "POST":
        code = (request.form.get("code") or "").strip() or None
        name = (request.form.get("name") or "").strip()
        section_id_raw = (request.form.get("section_id") or "").strip()
        start_time = (request.form.get("start_time") or "").strip() or None
        end_time = (request.form.get("end_time") or "").strip() or None
        late_after_raw = (request.form.get("late_after_minutes") or "0").strip()

        if not name:
            flash("กรุณากรอกชื่อวิชา", "error")
        elif not section_id_raw:
            flash("กรุณาเลือก Section", "error")
        elif not start_time or not end_time:
            flash("กรุณาระบุเวลาเริ่มเรียนและเวลาเลิกเรียน", "error")
        else:
            try:
                section_id = int(section_id_raw)
                late_after_minutes = max(0, int(late_after_raw or "0"))
                payload = {
                    "code": code,
                    "name": name,
                    "section_id": section_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "late_after_minutes": late_after_minutes,
                }
                db.supabase.table("subjects").insert(payload).execute()
                flash("เพิ่มวิชาและกำหนดเวลาเรียนสำเร็จ", "success")
            except Exception as exc:
                flash(f"เพิ่มวิชาไม่สำเร็จ: {exc}", "error")
        return redirect(url_for("subjects_page"))

    try:
        sections = _master_list("sections", "name")
    except Exception as exc:
        sections = []
        flash("อ่านตาราง sections ไม่สำเร็จ กรุณารัน SQL สำหรับ Master Data ก่อน: " + str(exc), "error")
    try:
        subjects = db.supabase.table("subjects").select("*, sections(name)").order("name").execute().data or []
    except Exception as exc:
        subjects = []
        flash("อ่านตาราง subjects ไม่สำเร็จ กรุณารัน SQL อัปเดตตารางก่อน: " + str(exc), "error")
    return render_template("subjects.html", subjects=subjects, sections=sections)

@app.route("/masters/subjects/<int:subject_id>/delete", methods=["POST"])
def subjects_delete(subject_id):
    try:
        db.supabase.table("subjects").delete().eq("id", subject_id).execute()
        flash("ลบวิชาสำเร็จ", "success")
    except Exception as exc:
        flash(f"ลบวิชาไม่สำเร็จ: {exc}", "error")
    return redirect(url_for("subjects_page"))


@app.route("/reports")
def reports_page():

    today = date.today()

    start_default = (
        today - timedelta(days=7)
    ).isoformat()

    end_default = today.isoformat()

    start_date = request.args.get(
        "start_date",
        start_default,
    )

    end_date = request.args.get(
        "end_date",
        end_default,
    )

    user_id = (
        request.args.get("user_id")
        or None
    )

    # -----------------------------------------------------
    # Get Logs
    # -----------------------------------------------------

    logs = db.get_logs_in_range(
        start_date,
        end_date,
        user_id,
    )

    users = db.get_all_users()

    # -----------------------------------------------------
    # Summary
    # -----------------------------------------------------

    summary = {}

    for row in logs:

        key = (
            row["student_id"]
            or "ไม่พบข้อมูลผู้ใช้"
        )

        if key not in summary:

            summary[key] = {
                "full_name": (
                    row["full_name"]
                    or "-"
                ),

                "department": (
                    row["department"]
                    or "-"
                ),

                "count": 0,

                "first": row["scanned_at"],

                "last": row["scanned_at"],
            }

        summary[key]["count"] += 1

        summary[key]["last"] = (
            row["scanned_at"]
        )

    return render_template(
        "reports.html",
        logs=logs,
        users=users,
        summary=summary,
        start_date=start_date,
        end_date=end_date,
        selected_user_id=user_id,
    )


# =========================================================
# Export Excel
# =========================================================

@app.route("/reports/export")
def reports_export():

    today = date.today()

    start_date = request.args.get(
        "start_date",
        (
            today - timedelta(days=7)
        ).isoformat(),
    )

    end_date = request.args.get(
        "end_date",
        today.isoformat(),
    )

    user_id = (
        request.args.get("user_id")
        or None
    )

    # -----------------------------------------------------
    # Get Logs
    # -----------------------------------------------------

    logs = db.get_logs_in_range(
        start_date,
        end_date,
        user_id,
    )

    # -----------------------------------------------------
    # Build Excel
    # -----------------------------------------------------

    excel_bytes = build_excel_report(
        logs,
        start_date,
        end_date,
    )

    filename = (
        f"attendance_report_"
        f"{start_date}_to_{end_date}.xlsx"
    )

    return send_file(
        io.BytesIO(excel_bytes),

        mimetype=(
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        ),

        as_attachment=True,

        download_name=filename,
    )




@app.route("/api/enroll", methods=["POST"])
def api_enroll():
    payload = request.get_json(silent=True) or {}
    fingerprint_id = str(payload.get("fingerprint_id", "")).strip()
    replace_existing = payload.get("replace_existing") is True

    if not fingerprint_id.isdigit():
        return jsonify({
            "error": "รหัสลายนิ้วมือต้องเป็นตัวเลข"
        }), 400

    # ถ้ามี Template อยู่แล้ว ต้องให้หน้าเว็บถามผู้ใช้ก่อนส่ง replace_existing=True
    try:
        has_template = db.has_fingerprint_template(fingerprint_id)
    except AttributeError:
        return jsonify({
            "error": "database.py ยังไม่มีฟังก์ชัน has_fingerprint_template()"
        }), 500
    except Exception as exc:
        print(f"[ENROLL] ตรวจสอบ Template ไม่สำเร็จ: {exc}")
        return jsonify({
            "error": "ตรวจสอบลายนิ้วมือเดิมใน Supabase ไม่สำเร็จ"
        }), 500

    if has_template and not replace_existing:
        return jsonify({
            "requires_confirmation": True,
            "fingerprint_id": fingerprint_id,
            "message": "ผู้ใช้นี้มีลายนิ้วมืออยู่แล้ว ต้องการเปลี่ยนลายนิ้วมือหรือไม่?"
        }), 409

    with enrollment_lock:
        if any(
            job["status"] in ("pending", "processing")
            for job in enrollment_jobs.values()
        ):
            return jsonify({
                "error": "มีงานลงทะเบียนที่กำลังดำเนินการอยู่"
            }), 409

        job_id = str(uuid.uuid4())

        job = {
            "job_id": job_id,
            "fingerprint_id": fingerprint_id,
            "replace_existing": replace_existing,
            "status": "pending",
            "message": "รอเครื่องสแกนรับงาน"
        }

        enrollment_jobs[job_id] = job
        scanner_queue.put(job.copy())

    return jsonify({
        "job_id": job_id,
        "status": "pending",
        "message": "ส่งคำขอลงทะเบียนแล้ว"
    }), 202



@app.route("/api/enroll/<job_id>", methods=["GET"])
def api_enroll_status(job_id):
    with enrollment_lock:
        job = enrollment_jobs.get(job_id)

        if not job:
            return jsonify({"error": "ไม่พบงานลงทะเบียน"}), 404

        return jsonify({
            "job_id": job["job_id"],
            "fingerprint_id": job["fingerprint_id"],
            "status": job["status"],
            "message": job["message"]
        })


@app.route("/api/scanner/enrollment/next", methods=["GET"])
def api_scanner_next_enrollment():
    with enrollment_lock:
        for job in enrollment_jobs.values():
            if job["status"] == "pending":
                job["status"] = "processing"
                job["message"] = "กรุณาวางนิ้วบนเครื่องสแกน 3 ครั้ง"
                return jsonify(job)

    return jsonify({"job": None})


@app.route("/api/scanner/enrollment/result", methods=["POST"])
def api_scanner_enrollment_result():
    payload = request.get_json(silent=True) or {}
    job_id = payload.get("job_id")
    success = payload.get("success") is True
    message = payload.get("message", "")

    with enrollment_lock:
        job = enrollment_jobs.get(job_id)

        if not job or job["status"] != "processing":
            return jsonify({"error": "ไม่พบงานหรือสถานะงานไม่ถูกต้อง"}), 404

        job["status"] = "success" if success else "failed"
        job["message"] = (
            message or (
                "ลงทะเบียนลายนิ้วมือสำเร็จ"
                if success else "ลงทะเบียนไม่สำเร็จ"
            )
        )

    return jsonify({"status": "ok"})

@app.route("/api/enroll/reset", methods=["POST"])
def api_enroll_reset():
    with enrollment_lock:
        for job in enrollment_jobs.values():
            if job["status"] in ("pending", "processing"):
                job["status"] = "failed"
                job["message"] = "ยกเลิกงานลงทะเบียนเดิมแล้ว"

    return jsonify({
        "status": "success",
        "message": "ยกเลิกงานลงทะเบียนที่ค้างแล้ว"
    })

# =========================================================
# WSGI → ASGI
# =========================================================


def get_attendance_status(subject_id, scanned_at):
    """
    คืนค่า on_time หรือ late ตามเวลาเริ่มเรียนและนาทีผ่อนผันของรายวิชา
    คืน None หากยังไม่ได้เลือกรายวิชา หรือไม่มีข้อมูลเวลาเริ่มเรียน
    """
    if subject_id is None or str(subject_id).strip() == "":
        return None

    response = (
        db.supabase.table("subjects")
        .select("id, name, start_time, late_after_minutes")
        .eq("id", int(subject_id))
        .limit(1)
        .execute()
    )
    subjects = response.data or []
    if not subjects:
        print(f"[ATTENDANCE DEBUG] ไม่พบ subject_id={subject_id}")
        return None

    subject = subjects[0]
    start_time_value = subject.get("start_time")
    if not start_time_value:
        print(
            f"[ATTENDANCE DEBUG] วิชา {subject_id} "
            "ไม่มี start_time"
        )
        return None

    # รองรับเวลาจากฐานข้อมูลทั้งรูปแบบ HH:MM และ HH:MM:SS
    start_time_text = str(start_time_value).strip()
    parsed_start_time = None
    for time_format in ("%H:%M:%S", "%H:%M"):
        try:
            parsed_start_time = datetime.strptime(
                start_time_text[:8] if time_format == "%H:%M:%S"
                else start_time_text[:5],
                time_format
            ).time()
            break
        except ValueError:
            continue

    if parsed_start_time is None:
        print(
            f"[ATTENDANCE ERROR] รูปแบบ start_time ไม่ถูกต้อง: "
            f"{start_time_value!r}"
        )
        return None

    try:
        scan_datetime = datetime.fromisoformat(
            str(scanned_at).replace("Z", "+00:00")
        )
    except (TypeError, ValueError):
        print(f"[ATTENDANCE ERROR] scanned_at ไม่ถูกต้อง: {scanned_at!r}")
        return None

    if scan_datetime.tzinfo is None:
        scan_datetime = scan_datetime.replace(tzinfo=THAI_TZ)
    else:
        scan_datetime = scan_datetime.astimezone(THAI_TZ)

    start_datetime = datetime.combine(
        scan_datetime.date(),
        parsed_start_time,
        tzinfo=THAI_TZ
    )

    try:
        grace_minutes = max(0, int(subject.get("late_after_minutes") or 0))
    except (TypeError, ValueError):
        grace_minutes = 0

    deadline = start_datetime + timedelta(minutes=grace_minutes)
    result = "on_time" if scan_datetime <= deadline else "late"

    print(
        f"[ATTENDANCE DEBUG] subject_id={subject_id}, "
        f"subject={subject.get('name')}, "
        f"start={start_datetime.isoformat()}, "
        f"deadline={deadline.isoformat()}, "
        f"scan={scan_datetime.isoformat()}, "
        f"result={result}"
    )
    return result


def scanner_worker():
    zk = ZKFP2()
    initialized = False
    opened = False
    templates = {}
    last_id = None
    last_time = 0.0

    def capture_template():
        # รอจนกว่าจะมีการวางนิ้ว
        while True:
            result = zk.AcquireFingerprint()

            if isinstance(result, (tuple, list)) and len(result) >= 2:
                template, _image = result

                if template:
                    return bytes(template)

            time.sleep(0.2)

    def enroll_with_sdk(job):
        job_id = job["job_id"]
        fingerprint_id = str(job["fingerprint_id"])
        fid = int(fingerprint_id)

        with enrollment_lock:
            enrollment_jobs[job_id]["status"] = "processing"
            enrollment_jobs[job_id]["message"] = (
                "กรุณาวางนิ้วบนเครื่องสแกน"
            )

        try:
            existing_template = templates.get(fingerprint_id)
            replace_existing = job.get("replace_existing") is True

            if existing_template and not replace_existing:
                raise ValueError(
                    "รหัสนี้มี Template อยู่แล้ว ต้องยืนยันเปลี่ยนลายนิ้วมือก่อน"
                )

            captures = []

            for index in range(3):
                with enrollment_lock:
                    enrollment_jobs[job_id]["message"] = (
                        f"กรุณาวางนิ้วครั้งที่ {index + 1}/3"
                    )

                print(
                    f"[SCANNER] รหัส {fingerprint_id}: "
                    f"วางนิ้วครั้งที่ {index + 1}/3"
                )

                captures.append(capture_template())
                print("[SCANNER] อ่านสำเร็จ กรุณานำนิ้วออก")
                time.sleep(1)

            merged, merged_length = zk.DBMerge(
                captures[0],
                captures[1],
                captures[2]
            )

            if not merged:
                raise RuntimeError("รวม Template ไม่สำเร็จ")

            merged = bytes(merged)

            if merged_length and len(merged) != int(merged_length):
                raise RuntimeError("ความยาว Template ไม่ถูกต้อง")
            # บันทึก Supabase ก่อน แล้วอัปเดต SDK; เก็บ Template เดิมไว้เผื่อ rollback
            template_base64 = base64.b64encode(merged).decode("ascii")
            db.update_fingerprint_template(fingerprint_id, template_base64)

            try:
                try:
                    zk.DBDel(fid)
                except Exception:
                    # DBDel อาจแจ้ง error เมื่อไม่มี ID อยู่ใน SDK
                    pass

                zk.DBAdd(fid, merged)
                templates[fingerprint_id] = merged
            except Exception:
                # ถ้า SDK อัปเดตไม่สำเร็จ ให้คืน Template เดิมใน SDK หากมี
                try:
                    zk.DBDel(fid)
                except Exception:
                    pass

                if existing_template:
                    try:
                        zk.DBAdd(fid, existing_template)
                        templates[fingerprint_id] = existing_template
                    except Exception as restore_exc:
                        print(
                            f"[SCANNER] คืน Template เดิมใน SDK ไม่สำเร็จ: "
                            f"{restore_exc}"
                        )
                else:
                    templates.pop(fingerprint_id, None)
                raise

            with enrollment_lock:
                enrollment_jobs[job_id]["status"] = "success"
                enrollment_jobs[job_id]["message"] = (
                    "ลงทะเบียนลายนิ้วมือสำเร็จ"
                )

            print(f"[SCANNER] ลงทะเบียน {fingerprint_id} สำเร็จ")

        except Exception as exc:
            with enrollment_lock:
                enrollment_jobs[job_id]["status"] = "failed"
                enrollment_jobs[job_id]["message"] = str(exc)

            print(f"[SCANNER] ลงทะเบียนไม่สำเร็จ: {exc}")

    try:
        zk.Init()
        initialized = True

        if not zk.GetDeviceCount():
            raise RuntimeError("ไม่พบเครื่องสแกน ZK9500")

        zk.OpenDevice(0)
        opened = True

        # โหลด Template จาก Supabase เท่านั้น ไม่ใช้ fingerprint_templates.json
        loaded_templates = db.get_all_fingerprint_templates() or {}
        templates = {}

        for fingerprint_id, template in loaded_templates.items():
            if template is None:
                continue

            if isinstance(template, str):
                # รองรับกรณี database.py คืนค่า Base64 string
                template_bytes = base64.b64decode(template, validate=True)
            else:
                template_bytes = bytes(template)

            normalized_id = str(fingerprint_id).strip()

            if not normalized_id.isdigit():
                raise ValueError(
                    f"Fingerprint ID ต้องเป็นตัวเลข: {normalized_id}"
                )

            if not template_bytes:
                raise ValueError(
                    f"Template ว่าง: fingerprint_id={normalized_id}"
                )

            try:
                zk.DBAdd(int(normalized_id), template_bytes)
                templates[normalized_id] = template_bytes
                print(
                    f"[SCANNER] โหลด Template {normalized_id} สำเร็จ"
                )
            except Exception as exc:
                print(
                    f"[SCANNER ERROR] โหลด Template ไม่สำเร็จ: "
                    f"id={normalized_id}, "
                    f"bytes={len(template_bytes)}, "
                    f"error={exc!r}"
                )
                raise

        scanner_status["ready"] = True
        scanner_status["error"] = None
        print("[SCANNER] เชื่อมต่อ ZK9500 สำเร็จ พร้อมใช้งาน")

        while True:
            try:
                job = scanner_queue.get_nowait()
            except queue.Empty:
                job = None

            if job:
                try:
                    enroll_with_sdk(job)
                finally:
                    scanner_queue.task_done()

                # ให้กลับไปสแกนเช็กชื่อหลังลงทะเบียน
                last_id = None
                last_time = 0.0
                continue

            result = zk.AcquireFingerprint()

            if not isinstance(result, (tuple, list)) or len(result) < 2:
                time.sleep(0.2)
                continue

            template, _image = result

            if not template:
                time.sleep(0.2)
                continue

            try:
                uid, score = zk.DBIdentify(bytes(template))

                if uid is None or int(uid) < 0:
                    continue

                fingerprint_id = str(uid)
                now = time.time()

                if (
                    fingerprint_id != last_id
                    or now - last_time >= 3
                ):
                    user = db.get_user_by_fingerprint(fingerprint_id)

                    scanned_at = datetime.now().astimezone().isoformat(
                        timespec="seconds"
                    )

                    with active_subject_lock:
                        subject_id = active_subject_id

                    if user:
                        attendance_status = get_attendance_status(
                            subject_id,
                            scanned_at
                        )
                        # matched หมายถึงพบผู้ใช้แต่ยังคำนวณสถานะเข้าเรียนไม่ได้
                        log_status = attendance_status or "matched"
                    else:
                        attendance_status = None
                        log_status = "unmatched"

                    print(
                        f"[SCAN DEBUG] fingerprint_id={fingerprint_id}, "
                        f"subject_id={subject_id}, "
                        f"attendance_status={attendance_status}, "
                        f"log_status={log_status}"
                    )

                    db.add_scan_log(
                        fingerprint_id,
                        user["id"] if user else None,
                        log_status,
                        scanned_at,
                        subject_id=subject_id,
                    )

                    print(
                        f"[SCANNER] {fingerprint_id}: "
                        f"{user['full_name'] if user else 'ไม่พบผู้ใช้'}"
                    )

                    last_id = fingerprint_id
                    last_time = now

            except Exception as exc:
                print(f"[SCANNER] ตรวจสอบลายนิ้วมือไม่สำเร็จ: {exc}")

            time.sleep(0.2)

    except Exception as exc:
        scanner_status["error"] = str(exc)
        print(f"[SCANNER ERROR] {exc}")

    finally:
        scanner_status["ready"] = False

        if opened:
            zk.CloseDevice()

        if initialized:
            zk.Terminate()

scanner_thread = threading.Thread(
    target=scanner_worker,
    name="ZK9500Scanner",
    daemon=True
)
scanner_thread.start()

asgi_app = WsgiToAsgi(app)