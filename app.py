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
import json
import time
from pathlib import Path
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

TEMPLATE_FILE = Path(__file__).resolve().parent / "fingerprint_templates.json"


def delete_fingerprint_template(fingerprint_id):
    if not TEMPLATE_FILE.exists():
        return

    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        templates = json.load(f)

    fingerprint_id = str(fingerprint_id)

    if fingerprint_id in templates:
        del templates[fingerprint_id]

        temp_file = TEMPLATE_FILE.with_suffix(".tmp")
        temp_file.write_text(
            json.dumps(templates, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_file.replace(TEMPLATE_FILE)

        print(f"[SCANNER] ลบ Template รหัส {fingerprint_id} จาก JSON แล้ว")



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
# =========================================================
# Dashboard
# =========================================================

@app.route("/")
def dashboard():
    logs = db.get_recent_logs(limit=50)

    return render_template(
        "index.html",
        logs=logs,
    )


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

    payload = request.get_json(
        silent=True
    ) or {}

    fingerprint_id = payload.get(
        "fingerprint_id"
    )

    scanned_at = (
        payload.get("scanned_at")
        or datetime.now().isoformat(
            timespec="seconds"
        )
    )

    if not fingerprint_id:
        return jsonify({
            "error": "ต้องระบุ fingerprint_id"
        }), 400

    # -----------------------------------------------------
    # ค้นหาผู้ใช้จาก Supabase
    # -----------------------------------------------------

    user = db.get_user_by_fingerprint(
        fingerprint_id
    )

    # -----------------------------------------------------
    # พบผู้ใช้
    # -----------------------------------------------------

    if user:

        db.add_scan_log(
            fingerprint_id,
            user["id"],
            "matched",
            scanned_at,
        )

        return jsonify({
            "status": "matched",
            "student_id": user["student_id"],
            "full_name": user["full_name"],
            "department": user["department"],
            "scanned_at": scanned_at,
        })

    # -----------------------------------------------------
    # ไม่พบผู้ใช้
    # -----------------------------------------------------

    db.add_scan_log(
        fingerprint_id,
        None,
        "unmatched",
        scanned_at,
    )

    return jsonify({
        "status": "unmatched",
        "scanned_at": scanned_at,
    }), 200


# =========================================================
# Users
# =========================================================

@app.route("/users")
def users_page():

    users = db.get_all_users()

    return render_template(
        "users.html",
        users=users,
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

        rows = []

        for values in sheet.iter_rows(min_row=2, values_only=True):
            row = dict(zip(headers, values))

            student_id = str(row.get("student_id") or "").strip()
            full_name = str(row.get("full_name") or "").strip()
            department = str(row.get("department") or "").strip()

            # ข้ามแถวว่าง
            if not student_id and not full_name and not department:
                continue

            rows.append({
                "student_id": student_id,
                "full_name": full_name,
                "department": department
            })

        workbook.close()

        result = db.import_users_from_excel(rows)

        flash(
            f"นำเข้าสำเร็จ {result['inserted']} คน, "
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

    if not fingerprint_id.isdigit():
        return jsonify({
            "error": "รหัสลายนิ้วมือต้องเป็นตัวเลข"
        }), 400

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



def scanner_worker():
    zk = ZKFP2()
    initialized = False
    opened = False
    templates = {}
    last_id = None
    last_time = 0.0

    template_file = Path(__file__).with_name(
        "fingerprint_templates.json"
    )

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
            if fingerprint_id in templates:
                raise ValueError(
                    "รหัสนี้มี Template อยู่แล้ว กรุณาตรวจสอบก่อนลงทะเบียนใหม่"
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
            zk.DBAdd(fid, merged)
            template_base64 = base64.b64encode(
                merged
            ).decode("ascii")
            db.update_fingerprint_template(
                fingerprint_id,
                template_base64
            )
            templates[fingerprint_id] = template_base64

            try:
                temp_file = template_file.with_suffix(".tmp")
                temp_file.write_text(
                    json.dumps(templates, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
                temp_file.replace(template_file)
            except Exception:
                # ยกเลิกการลงทะเบียนใน SDK หากบันทึกไฟล์ไม่ได้
                try:
                    zk.DBDel(fid)
                except Exception:
                    pass

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

        if template_file.exists():
            templates = json.loads(
                template_file.read_text(encoding="utf-8")
            )

        for fingerprint_id, encoded in templates.items():
            zk.DBAdd(
                int(fingerprint_id),
                base64.b64decode(encoded)
            )

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

                    db.add_scan_log(
                        fingerprint_id,
                        user["id"] if user else None,
                        "matched" if user else "unmatched",
                        scanned_at
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