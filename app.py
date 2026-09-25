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

from datetime import datetime, date, timedelta
import io

import database as db
from report import build_excel_report


# =========================================================
# Flask App
# =========================================================

app = Flask(__name__)

app.secret_key = "change-this-secret-key"


# =========================================================
# Supabase
# =========================================================

db.init_db()


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

        db.add_user(
            student_id,
            full_name,
            department,
            fingerprint_id,
        )

        flash(
            f"เพิ่มผู้ใช้ {full_name} สำเร็จ",
            "success",
        )

    except Exception as exc:

        print(
            f"[ERROR] เพิ่มผู้ใช้ไม่สำเร็จ: {exc}"
        )

        flash(
            f"เพิ่มผู้ใช้ไม่สำเร็จ: "
            f"รหัสนักศึกษาหรือรหัสลายนิ้วมือซ้ำ "
            f"({exc})",
            "error",
        )

    return redirect(
        url_for("users_page")
    )


@app.route(
    "/users/delete/<int:user_id>",
    methods=["POST"],
)
def users_delete(user_id):

    try:

        db.delete_user(user_id)

        flash(
            "ลบผู้ใช้เรียบร้อยแล้ว",
            "success",
        )

    except Exception as exc:

        print(
            f"[ERROR] ลบผู้ใช้ไม่สำเร็จ: {exc}"
        )

        flash(
            f"ลบผู้ใช้ไม่สำเร็จ: {exc}",
            "error",
        )

    return redirect(
        url_for("users_page")
    )


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


# =========================================================
# WSGI → ASGI
# =========================================================

asgi_app = WsgiToAsgi(app)