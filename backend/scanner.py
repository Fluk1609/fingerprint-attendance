import base64
import hmac
import os
import time
import threading

from dotenv import load_dotenv
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from pyzkfp import ZKFP2

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

app = Flask(__name__)

FRONTEND_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://fingerprint-attendance.app",
    "https://fingerprint-attendances.vercel.app",
    "https://fingerprint-attendance-seven.vercel.app",
]

CLOUD_API_URL = os.getenv("CLOUD_API_URL", "").rstrip("/")
SCANNER_AGENT_TOKEN = os.getenv("SCANNER_AGENT_TOKEN", "")

CORS(app, resources={r"/api/scanner/*": {"origins": FRONTEND_ORIGINS}})

enrollment = {"active": False, "user_id": None, "templates": []}
scanner_lock = threading.Lock()


def cloud_headers():
    if not CLOUD_API_URL or not SCANNER_AGENT_TOKEN:
        raise RuntimeError("ยังไม่ได้ตั้งค่า CLOUD_API_URL หรือ SCANNER_AGENT_TOKEN")
    return {"X-Scanner-Agent-Token": SCANNER_AGENT_TOKEN}


def capture_fingerprint(timeout=30):
    zkfp = ZKFP2()
    sdk_initialized = False
    device_opened = False
    try:
        zkfp.Init()
        sdk_initialized = True
        zkfp.OpenDevice(0)
        device_opened = True

        started_at = time.time()
        while time.time() - started_at < timeout:
            result = zkfp.AcquireFingerprint()
            if result:
                template, _image = result
                template_bytes = bytes(template)
                if template_bytes:
                    return template_bytes
            time.sleep(0.2)
        raise TimeoutError("หมดเวลารอสแกนลายนิ้วมือ กรุณาลองอีกครั้ง")
    finally:
        if device_opened:
            try:
                zkfp.CloseDevice()
            except Exception:
                app.logger.exception("Unable to close scanner device")
        if sdk_initialized:
            try:
                zkfp.Terminate()
            except Exception:
                app.logger.exception("Unable to terminate scanner SDK")


def identify_fingerprint(captured_template, enrolled_templates):
    """Load enrolled templates into the SDK and identify the captured template."""
    zkfp = ZKFP2()
    sdk_initialized = False
    device_opened = False
    db_initialized = False
    try:
        zkfp.Init()
        sdk_initialized = True
        zkfp.OpenDevice(0)
        device_opened = True
        zkfp.DBInit()
        db_initialized = True

        loaded_count = 0
        for item in enrolled_templates:
            try:
                fid = int(item["fingerprint_id"])
                template = base64.b64decode(item["template"], validate=True)
                if not template:
                    continue
                result = zkfp.DBAdd(fid, template)
                # pyzkfp commonly returns 0 on success; None is also accepted by wrappers.
                if result not in (None, 0, True):
                    app.logger.warning("DBAdd returned %r for fingerprint_id=%s", result, fid)
                    continue
                loaded_count += 1
            except Exception:
                app.logger.exception("Unable to load one fingerprint template")

        if loaded_count == 0:
            raise RuntimeError("ยังไม่มีข้อมูลลายนิ้วมือที่ลงทะเบียนไว้ในระบบ")

        result = zkfp.DBIdentify(captured_template)
        if result is None:
            return None

        # pyzkfp versions commonly return (fid, score). Also tolerate (ret, fid, score).
        if isinstance(result, (tuple, list)):
            if len(result) >= 3:
                fid, score = result[-2], result[-1]
            elif len(result) == 2:
                fid, score = result
            elif len(result) == 1:
                fid, score = result[0], None
            else:
                return None
        else:
            fid, score = result, None

        try:
            fid = int(fid)
        except (TypeError, ValueError):
            return None

        if fid < 0:
            return None
        return {"fingerprint_id": str(fid), "score": score}
    finally:
        if db_initialized:
            try:
                zkfp.DBFree()
            except Exception:
                app.logger.exception("Unable to free scanner DB")
        if device_opened:
            try:
                zkfp.CloseDevice()
            except Exception:
                app.logger.exception("Unable to close scanner device")
        if sdk_initialized:
            try:
                zkfp.Terminate()
            except Exception:
                app.logger.exception("Unable to terminate scanner SDK")


@app.get("/api/scanner/health")
def scanner_health():
    zkfp = ZKFP2()
    initialized = False
    try:
        zkfp.Init()
        initialized = True
        count = zkfp.GetDeviceCount()
        return jsonify({
            "success": True,
            "connected": count > 0,
            "device_count": count,
            "message": "Scanner is ready" if count > 0 else "No fingerprint scanner detected"
        }), 200
    except Exception:
        app.logger.exception("Scanner health check failed")
        return jsonify({"success": False, "connected": False,
                        "message": "ไม่สามารถตรวจสอบเครื่องสแกนได้"}), 500
    finally:
        if initialized:
            try:
                zkfp.Terminate()
            except Exception:
                app.logger.exception("Unable to terminate scanner SDK")


@app.post("/api/scanner/enroll/start")
def enroll_start():
    payload = request.get_json(silent=True) or {}
    try:
        user_id = int(payload.get("user_id"))
        if user_id <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "user_id ไม่ถูกต้อง"}), 400

    with scanner_lock:
        if enrollment["active"]:
            return jsonify({"success": False, "message": "มีการลงทะเบียนลายนิ้วมือรายการอื่นอยู่"}), 409
        enrollment.update({"active": True, "user_id": user_id, "templates": []})

    return jsonify({"success": True, "message": "เริ่มลงทะเบียนแล้ว กรุณาสแกนนิ้วเดิม 3 ครั้ง",
                    "scan_count": 0, "required_scans": 3}), 200


@app.post("/api/scanner/enroll/capture")
def enroll_capture():
    with scanner_lock:
        if not enrollment["active"]:
            return jsonify({"success": False, "message": "กรุณาเริ่มลงทะเบียนก่อน"}), 400
        if len(enrollment["templates"]) >= 3:
            return jsonify({"success": False, "message": "สแกนครบ 3 ครั้งแล้ว"}), 400
        try:
            template = capture_fingerprint(timeout=30)
            enrollment["templates"].append(template)
            count = len(enrollment["templates"])
            return jsonify({"success": True, "message": f"สแกนครั้งที่ {count}/3 สำเร็จ",
                            "scan_count": count, "required_scans": 3,
                            "completed": count == 3}), 200
        except TimeoutError as exc:
            return jsonify({"success": False, "message": str(exc)}), 408
        except Exception:
            app.logger.exception("Fingerprint capture failed")
            return jsonify({"success": False, "message": "เกิดข้อผิดพลาดระหว่างอ่านลายนิ้วมือ"}), 500


@app.post("/api/scanner/enroll/finish")
def enroll_finish():
    with scanner_lock:
        if not enrollment["active"]:
            return jsonify({"success": False, "message": "ไม่มีรายการลงทะเบียนที่กำลังทำงาน"}), 400
        if len(enrollment["templates"]) != 3:
            return jsonify({"success": False, "message": "ต้องสแกนให้ครบ 3 ครั้ง",
                            "scan_count": len(enrollment["templates"])}), 400

        zkfp = ZKFP2()
        sdk_initialized = device_opened = db_initialized = False
        try:
            cloud_headers()
            zkfp.Init()
            sdk_initialized = True
            zkfp.OpenDevice(0)
            device_opened = True
            zkfp.DBInit()
            db_initialized = True

            registered_template, template_length = zkfp.DBMerge(
                enrollment["templates"][0],
                enrollment["templates"][1],
                enrollment["templates"][2]
            )
            template_bytes = bytes(registered_template)[:template_length]
            if not template_bytes:
                raise RuntimeError("ไม่สามารถสร้าง Fingerprint Template ได้")

            user_id = enrollment["user_id"]
            response = requests.put(
                f"{CLOUD_API_URL}/api/users/{user_id}/fingerprint",
                json={"template": base64.b64encode(template_bytes).decode("ascii")},
                headers=cloud_headers(),
                timeout=30
            )
            try:
                cloud_result = response.json()
            except ValueError:
                cloud_result = {}
            if not response.ok:
                raise RuntimeError(cloud_result.get("message") or
                                   f"Cloud API ตอบกลับ HTTP {response.status_code}")

            enrollment.update({"active": False, "user_id": None, "templates": []})
            return jsonify({"success": True,
                            "message": cloud_result.get("message", "ลงทะเบียนลายนิ้วมือสำเร็จ"),
                            "user_id": user_id}), 200
        except requests.RequestException:
            app.logger.exception("Unable to save fingerprint to cloud API")
            return jsonify({"success": False,
                            "message": "ไม่สามารถเชื่อมต่อ Cloud API เพื่อบันทึกลายนิ้วมือได้"}), 502
        except Exception as exc:
            app.logger.exception("Fingerprint enrollment failed")
            return jsonify({"success": False, "message": str(exc)}), 500
        finally:
            if db_initialized:
                try: zkfp.DBFree()
                except Exception: app.logger.exception("Unable to free scanner DB")
            if device_opened:
                try: zkfp.CloseDevice()
                except Exception: app.logger.exception("Unable to close scanner")
            if sdk_initialized:
                try: zkfp.Terminate()
                except Exception: app.logger.exception("Unable to terminate scanner SDK")


@app.post("/api/scanner/checkin")
def scanner_checkin():
    """Capture one fingerprint, identify it against Cloud templates, then record attendance."""
    with scanner_lock:
        try:
            headers = cloud_headers()
            templates_response = requests.get(
                f"{CLOUD_API_URL}/api/checkin/fingerprint-templates",
                headers=headers,
                timeout=30
            )
            try:
                templates_data = templates_response.json()
            except ValueError:
                templates_data = {}
            if not templates_response.ok:
                return jsonify({"success": False,
                                "message": templates_data.get("message") or
                                           f"โหลดข้อมูลลายนิ้วมือไม่สำเร็จ (HTTP {templates_response.status_code})"}), 502

            enrolled_templates = templates_data.get("templates", [])
            if not enrolled_templates:
                return jsonify({"success": False,
                                "message": "ยังไม่มีผู้ใช้ลงทะเบียนลายนิ้วมือ"}), 404

            captured = capture_fingerprint(timeout=30)
            matched = identify_fingerprint(captured, enrolled_templates)
            if not matched:
                return jsonify({"success": False,
                                "matched": False,
                                "message": "ไม่พบลายนิ้วมือในระบบ กรุณาลองอีกครั้ง"}), 404

            record_response = requests.post(
                f"{CLOUD_API_URL}/api/checkin/record",
                json={"fingerprint_id": matched["fingerprint_id"]},
                headers=headers,
                timeout=30
            )
            try:
                record_data = record_response.json()
            except ValueError:
                record_data = {}
            if not record_response.ok:
                return jsonify({"success": False,
                                "message": record_data.get("message") or
                                           f"บันทึกเวลาเข้าเรียนไม่สำเร็จ (HTTP {record_response.status_code})"}), 502

            return jsonify({
                "success": True,
                "matched": True,
                "score": matched.get("score"),
                "user": record_data.get("user"),
                "attendance": record_data.get("attendance"),
                "message": record_data.get("message", "เช็คชื่อสำเร็จ")
            }), 200
        except TimeoutError as exc:
            return jsonify({"success": False, "message": str(exc)}), 408
        except requests.RequestException:
            app.logger.exception("Cloud API request failed during check-in")
            return jsonify({"success": False, "message": "ไม่สามารถเชื่อมต่อ Cloud API ได้"}), 502
        except Exception as exc:
            app.logger.exception("Fingerprint check-in failed")
            return jsonify({"success": False, "message": str(exc)}), 500


@app.post("/api/scanner/enroll/cancel")
def enroll_cancel():
    with scanner_lock:
        enrollment.update({"active": False, "user_id": None, "templates": []})
    return jsonify({"success": True, "message": "ยกเลิกการลงทะเบียนแล้ว"}), 200


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False, threaded=True)
