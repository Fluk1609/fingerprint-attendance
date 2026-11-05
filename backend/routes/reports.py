from io import BytesIO
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request, send_file
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import current_app
from config.database import supabase

reports_bp = Blueprint("reports", __name__)
THAI_TZ = ZoneInfo("Asia/Bangkok")


def _parse_date(value, field_name):
    if not value:
        raise ValueError(f"กรุณาระบุ{field_name}")
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"รูปแบบ{field_name}ไม่ถูกต้อง")


def _load_report_rows(start_date, end_date, user_id=None, semester_id=None):
    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=THAI_TZ)
    end_exclusive = datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=THAI_TZ)

    query = (
        supabase.table("scan_logs")
        .select("""
            id, user_id, subject_id, semester_id, scanned_at, status,
            users (student_id, full_name, department),
            subjects (code, name)
        """)
        .gte("scanned_at", start_dt.isoformat())
        .lt("scanned_at", end_exclusive.isoformat())
        .order("scanned_at", desc=False)
    )
    if user_id:
        query = query.eq("user_id", int(user_id))
    if semester_id:
        query = query.eq("semester_id", int(semester_id))

    rows = []
    offset = 0
    page_size = 1000
    while True:
        response = query.range(offset, offset + page_size - 1).execute()
        batch = response.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def _build_summary(rows):
    summary = {}
    for row in rows:
        user = row.get("users") or {}
        user_id = row.get("user_id")
        key = str(user_id) if user_id is not None else f"unknown-{row.get('id')}"
        item = summary.setdefault(key, {
            "user_id": user_id,
            "student_id": user.get("student_id") or "-",
            "full_name": user.get("full_name") or "ไม่พบข้อมูลผู้ใช้",
            "department": user.get("department") or "-",
            "count": 0,
            "on_time_count": 0,
            "late_count": 0,
            "last": None,
        })
        item["count"] += 1
        if row.get("status") == "on_time":
            item["on_time_count"] += 1
        elif row.get("status") == "late":
            item["late_count"] += 1
        scanned_at = row.get("scanned_at")
        if scanned_at and (not item["last"] or scanned_at > item["last"]):
            item["last"] = scanned_at

    return sorted(summary.values(), key=lambda x: (x["student_id"], x["full_name"]))


@reports_bp.route("/api/reports", methods=["GET"])
def get_reports():
    try:
        start_date = _parse_date(request.args.get("start_date"), "วันที่เริ่มต้น")
        end_date = _parse_date(request.args.get("end_date"), "วันที่สิ้นสุด")
        if start_date > end_date:
            return jsonify({"success": False, "message": "วันที่เริ่มต้นต้องไม่เกินวันที่สิ้นสุด"}), 400

        user_id = request.args.get("user_id") or None
        semester_id = request.args.get("semester_id") or None
        rows = _load_report_rows(start_date, end_date, user_id, semester_id)
        summary = _build_summary(rows)

        totals = {
            "total_scans": len(rows),
            "on_time": sum(1 for row in rows if row.get("status") == "on_time"),
            "late": sum(1 for row in rows if row.get("status") == "late"),
            "unmatched": sum(1 for row in rows if row.get("status") == "unmatched"),
            "people": len({str(row.get("user_id")) for row in rows if row.get("user_id") is not None}),
        }

        return jsonify({
            "success": True,
            "filters": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "user_id": int(user_id) if user_id else None,
                "semester_id": int(semester_id) if semester_id else None,
            },
            "totals": totals,
            "summary": summary,
            "logs": [{
                "id": row.get("id"),
                "scanned_at": row.get("scanned_at"),
                "status": row.get("status"),
                "student_id": (row.get("users") or {}).get("student_id"),
                "full_name": (row.get("users") or {}).get("full_name"),
                "department": (row.get("users") or {}).get("department"),
                "subject_code": (row.get("subjects") or {}).get("code"),
                "subject_name": (row.get("subjects") or {}).get("name"),
            } for row in rows]
        }), 200
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400
    except Exception:
        reports_bp.logger.exception("Unable to create attendance report")
        return jsonify({"success": False, "message": "ไม่สามารถค้นหารายงานได้"}), 500

def _to_thai_datetime(value):
    if not value:
        return None

    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

    # หากไม่มี timezone ให้ถือว่าเป็น UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))

    # แปลงเป็นเวลาไทย และตัด timezone ออกเพื่อให้ Excel รองรับ
    return dt.astimezone(
        ZoneInfo("Asia/Bangkok")
    ).replace(tzinfo=None)

@reports_bp.route("/api/reports/export", methods=["GET"])
def export_reports():
    try:
        start_date = _parse_date(
            request.args.get("start_date"), "วันที่เริ่มต้น"
        )
        end_date = _parse_date(
            request.args.get("end_date"), "วันที่สิ้นสุด"
        )

        if start_date > end_date:
            return jsonify({
                "success": False,
                "message": "วันที่เริ่มต้นต้องไม่เกินวันที่สิ้นสุด"
            }), 400

        rows = _load_report_rows(
            start_date,
            end_date,
            request.args.get("user_id") or None,
            request.args.get("semester_id") or None
        )

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Attendance Report"

        sheet.append([
            "รหัส",
            "ชื่อ-นามสกุล",
            "หน่วยงาน/สาขา",
            "รายวิชา",
            "วันที่และเวลา",
            "สถานะ"
        ])

        for row in rows:
            user = row.get("users") or {}
            subject = row.get("subjects") or {}

            scanned_at = _to_thai_datetime(
                row.get("scanned_at")
            )

            sheet.append([
                user.get("student_id") or "-",
                user.get("full_name") or "ไม่พบข้อมูลผู้ใช้",
                user.get("department") or "-",
                " - ".join(filter(None, [
                    subject.get("code"),
                    subject.get("name")
                ])) or "-",
                scanned_at or "-",
                {
                    "on_time": "ตรงเวลา",
                    "late": "มาสาย",
                    "unmatched": "ไม่พบผู้ใช้"
                }.get(
                    row.get("status"),
                    row.get("status") or "-"
                )
            ])

            # กำหนดรูปแบบวันที่และเวลาใน Excel
            date_cell = sheet.cell(
                row=sheet.max_row,
                column=5
            )

            if isinstance(date_cell.value, datetime):
                date_cell.number_format = "dd/mm/yyyy hh:mm:ss"

        # รูปแบบ Header
        header_fill = PatternFill(
            "solid",
            fgColor="1F4E78"
        )

        for cell in sheet[1]:
            cell.font = Font(
                bold=True,
                color="FFFFFF"
            )
            cell.fill = header_fill
            cell.alignment = Alignment(
                horizontal="center"
            )

        # ปรับความกว้าง Column
        for column_cells in sheet.columns:
            max_length = max(
                len(str(cell.value or ""))
                for cell in column_cells
            )

            column_letter = get_column_letter(
                column_cells[0].column
            )

            sheet.column_dimensions[column_letter].width = min(
                max(max_length + 3, 14),
                42
            )

        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions

        output = BytesIO()
        workbook.save(output)
        output.seek(0)

        filename = (
            f"attendance_report_{start_date:%Y%m%d}_"
            f"{end_date:%Y%m%d}.xlsx"
        )

        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except ValueError as exc:
        return jsonify({
            "success": False,
            "message": str(exc)
        }), 400

    except Exception:
        current_app.logger.exception(
            "Unable to export attendance report"
        )

        return jsonify({
            "success": False,
            "message": "ไม่สามารถ Export รายงานได้"
        }), 500