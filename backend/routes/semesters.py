
from flask import Blueprint, jsonify, request, current_app
from datetime import date

from config.database import supabase

semesters_bp = Blueprint("semesters", __name__)


# =========================================================
# Helper: Validate Semester
# =========================================================

def validate_semester(payload, exclude_id=None):
    semester_name = str(
        payload.get("semester_name") or ""
    ).strip()

    start_date = str(
        payload.get("start_date") or ""
    ).strip()

    end_date = str(
        payload.get("end_date") or ""
    ).strip()

    if not semester_name:
        raise ValueError("กรุณาระบุชื่อภาคเรียน")

    if not start_date or not end_date:
        raise ValueError("กรุณาระบุวันที่เริ่มต้นและสิ้นสุด")

    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError:
        raise ValueError("รูปแบบวันที่ไม่ถูกต้อง")

    if start > end:
        raise ValueError("วันสิ้นสุดต้องไม่น้อยกว่าวันเริ่มต้น")

    # ตรวจสอบชื่อภาคเรียนซ้ำ
    query = (
        supabase.table("semesters")
        .select("id")
        .eq("semester_name", semester_name)
    )

    # กรณีแก้ไข ไม่ตรวจสอบ ID ของตัวเอง
    if exclude_id is not None:
        query = query.neq("id", exclude_id)

    if query.execute().data:
        raise ValueError("ชื่อภาคเรียนนี้มีอยู่แล้ว")

    return {
        "semester_name": semester_name,
        "start_date": start.isoformat(),
        "end_date": end.isoformat()
    }


# =========================================================
# Helper: Check Semester Exists
# =========================================================

def get_semester(semester_id):
    response = (
        supabase.table("semesters")
        .select("*")
        .eq("id", semester_id)
        .limit(1)
        .execute()
    )

    return response.data[0] if response.data else None


# =========================================================
# GET: All Semesters
# =========================================================

@semesters_bp.route("/api/semesters", methods=["GET"])
def get_semesters():
    try:
        response = (
            supabase.table("semesters")
            .select("*")
            .order("start_date", desc=True)
            .execute()
        )

        return jsonify(response.data or []), 200

    except Exception:
        current_app.logger.exception(
            "Unable to retrieve semesters"
        )

        return jsonify({
            "success": False,
            "message": "ไม่สามารถดึงข้อมูลภาคเรียนได้"
        }), 500


# =========================================================
# GET: Active Semester
# =========================================================

@semesters_bp.route("/api/semesters/active", methods=["GET"])
def get_active_semester():
    try:
        response = (
            supabase.table("semesters")
            .select("*")
            .eq("is_active", True)
            .limit(1)
            .execute()
        )

        if not response.data:
            return jsonify({
                "success": True,
                "active": False,
                "semester": None
            }), 200

        return jsonify({
            "success": True,
            "active": True,
            "semester": response.data[0]
        }), 200

    except Exception:
        current_app.logger.exception(
            "Unable to retrieve active semester"
        )

        return jsonify({
            "success": False,
            "message": "ไม่สามารถดึงภาคเรียนปัจจุบันได้"
        }), 500


# =========================================================
# POST: Create Semester
# =========================================================

@semesters_bp.route("/api/semesters", methods=["POST"])
def create_semester():
    payload = request.get_json(silent=True) or {}

    try:
        semester_data = validate_semester(payload)

        response = (
            supabase.table("semesters")
            .insert({
                **semester_data,
                "is_active": False
            })
            .execute()
        )

        if not response.data:
            raise Exception("Semester insert returned no data")

        return jsonify({
            "success": True,
            "message": "สร้างภาคเรียนสำเร็จ",
            "semester": response.data[0]
        }), 201

    except ValueError as exc:
        return jsonify({
            "success": False,
            "message": str(exc)
        }), 400

    except Exception:
        current_app.logger.exception(
            "Unable to create semester"
        )

        return jsonify({
            "success": False,
            "message": "ไม่สามารถสร้างภาคเรียนได้"
        }), 500


# =========================================================
# PUT: Update Semester
# =========================================================

@semesters_bp.route(
    "/api/semesters/<int:semester_id>",
    methods=["PUT"]
)
def update_semester(semester_id):
    payload = request.get_json(silent=True) or {}

    try:
        existing = get_semester(semester_id)

        if not existing:
            return jsonify({
                "success": False,
                "message": "ไม่พบภาคเรียน"
            }), 404

        if existing.get("is_active"):
            return jsonify({
                "success": False,
                "message": "กรุณาปิดภาคเรียนก่อนแก้ไขข้อมูล"
            }), 409

        semester_data = validate_semester(
            payload,
            exclude_id=semester_id
        )

        response = (
            supabase.table("semesters")
            .update(semester_data)
            .eq("id", semester_id)
            .execute()
        )

        return jsonify({
            "success": True,
            "message": "แก้ไขภาคเรียนสำเร็จ",
            "semester": response.data[0] if response.data else None
        }), 200

    except ValueError as exc:
        return jsonify({
            "success": False,
            "message": str(exc)
        }), 400

    except Exception:
        current_app.logger.exception(
            "Unable to update semester"
        )

        return jsonify({
            "success": False,
            "message": "ไม่สามารถแก้ไขภาคเรียนได้"
        }), 500


# =========================================================
# PUT: Activate Semester
# =========================================================

@semesters_bp.route(
    "/api/semesters/<int:semester_id>/activate",
    methods=["PUT"]
)
def activate_semester(semester_id):
    try:
        existing = get_semester(semester_id)

        if not existing:
            return jsonify({
                "success": False,
                "message": "ไม่พบภาคเรียน"
            }), 404

        if existing.get("is_active"):
            return jsonify({
                "success": True,
                "message": "ภาคเรียนนี้กำลังใช้งานอยู่แล้ว"
            }), 200

        supabase.rpc(
            "activate_semester",
            {"p_semester_id": semester_id}
        ).execute()

        return jsonify({
            "success": True,
            "message": "เปิดใช้งานภาคเรียนสำเร็จ"
        }), 200

    except Exception:
        current_app.logger.exception(
            "Unable to activate semester"
        )

        return jsonify({
            "success": False,
            "message": "ไม่สามารถเปิดใช้งานภาคเรียนได้"
        }), 500


# =========================================================
# PUT: Close Semester
# =========================================================

@semesters_bp.route(
    "/api/semesters/<int:semester_id>/close",
    methods=["PUT"]
)
def close_semester(semester_id):
    try:
        existing = get_semester(semester_id)

        if not existing:
            return jsonify({
                "success": False,
                "message": "ไม่พบภาคเรียน"
            }), 404

        if not existing.get("is_active"):
            return jsonify({
                "success": True,
                "message": "ภาคเรียนนี้ปิดใช้งานอยู่แล้ว"
            }), 200

        supabase.rpc(
            "close_semester",
            {"p_semester_id": semester_id}
        ).execute()

        return jsonify({
            "success": True,
            "message": "ปิดภาคเรียนสำเร็จ"
        }), 200

    except Exception:
        current_app.logger.exception(
            "Unable to close semester"
        )

        return jsonify({
            "success": False,
            "message": "ไม่สามารถปิดภาคเรียนได้"
        }), 500


# =========================================================
# DELETE: Delete Semester
# =========================================================

@semesters_bp.route(
    "/api/semesters/<int:semester_id>",
    methods=["DELETE"]
)
def delete_semester(semester_id):
    try:
        existing = get_semester(semester_id)

        if not existing:
            return jsonify({
                "success": False,
                "message": "ไม่พบภาคเรียน"
            }), 404

        # ป้องกันการลบภาคเรียนที่กำลังใช้งาน
        if existing.get("is_active"):
            return jsonify({
                "success": False,
                "message": "ไม่สามารถลบภาคเรียนที่เปิดใช้งานอยู่ได้"
            }), 409

        logs = (
            supabase.table("scan_logs")
            .select("id")
            .eq("semester_id", semester_id)
            .limit(1)
            .execute()
        )
        if logs.data:
            return jsonify({
                "success": False,
                "message": "ไม่สามารถลบภาคเรียนนี้ได้ เนื่องจากมีประวัติการเช็กชื่อ"
            }), 409

        supabase.table("semesters") \
            .delete() \
            .eq("id", semester_id) \
            .execute()

        return jsonify({
            "success": True,
            "message": "ลบภาคเรียนสำเร็จ"
        }), 200

    except Exception:
        current_app.logger.exception(
            "Unable to delete semester"
        )

        return jsonify({
            "success": False,
            "message": "ไม่สามารถลบภาคเรียนได้"
        }), 500
