import base64
import hmac
import os
import sys
import time
import threading
import secrets

from dotenv import load_dotenv
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from pyzkfp import ZKFP2

# Config is kept outside the executable so secrets can be rotated without rebuilding.
if getattr(sys, "frozen", False):
    AGENT_DIR = os.path.dirname(sys.executable)
else:
    AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(AGENT_DIR, "config", ".env")
load_dotenv(CONFIG_PATH)


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
LOCAL_PAIRING_CODE = os.getenv("LOCAL_PAIRING_CODE", "")
LOCAL_SESSION_TTL = int(os.getenv("LOCAL_SESSION_TTL", "28800"))
LOCAL_SESSION_TOKEN = None
LOCAL_SESSION_EXPIRES = 0


CORS(app, resources={r"/api/scanner/*": {"origins": FRONTEND_ORIGINS}})

enrollment = {"active": False, "user_id": None, "templates": []}

# Lock สำหรับป้องกันการเรียก ZKFP2 SDK พร้อมกัน
scanner_lock = threading.Lock()

# Last-known scanner status
scanner_status = {
    "connected": False,
    "device_count": 0,
    "message": "Scanner is not initialized"
}


def set_scanner_status(connected, device_count=0, message=None):
    global scanner_status

    scanner_status = {
        "connected": bool(connected),
        "device_count": int(device_count),
        "message": message or (
            "Scanner is ready"
            if connected
            else "No fingerprint scanner detected"
        )
    }


def cloud_headers():
    if not CLOUD_API_URL or not SCANNER_AGENT_TOKEN:
        raise RuntimeError("ยังไม่ได้ตั้งค่า CLOUD_API_URL หรือ SCANNER_AGENT_TOKEN")
    return {"X-Scanner-Agent-Token": SCANNER_AGENT_TOKEN}


def capture_fingerprint(timeout=30, reconnect_timeout=60, retry_interval=2):
    """
    Capture one fingerprint with USB hot-plug recovery.

    - If no finger is placed while the scanner remains connected, raise TimeoutError.
    - If Init/OpenDevice/AcquireFingerprint fails because the scanner is unplugged,
      release what can be released and retry from a fresh ZKFP2 instance.
    - After reconnect_timeout, raise ConnectionError for the API handler.
    """
    reconnect_deadline = time.monotonic() + reconnect_timeout
    last_error = None

    while time.monotonic() < reconnect_deadline:
        zkfp = None
        sdk_initialized = False
        device_opened = False

        try:
            # Construct a fresh wrapper on every retry. Some SDK states cannot be reused
            # after the USB device has been removed.
            zkfp = ZKFP2()
            zkfp.Init()
            sdk_initialized = True

            device_count = zkfp.GetDeviceCount()

            if not device_count:
                set_scanner_status(
                    False,
                    0,
                    "No fingerprint scanner detected"
                )
                raise ConnectionError("ไม่พบเครื่องสแกนลายนิ้วมือ")

            set_scanner_status(
                True,
                device_count,
                "Scanner is ready"
            )

            zkfp.OpenDevice(0)
            device_opened = True

            scan_deadline = time.monotonic() + timeout
            while time.monotonic() < scan_deadline:
                # USB removal may make either this call or AcquireFingerprint fail.
                if zkfp.GetDeviceCount() <= 0:
                    raise ConnectionError("เครื่องสแกนถูกถอดออก")

                result = zkfp.AcquireFingerprint()
                if result:
                    template, _image = result
                    template_bytes = bytes(template)
                    if template_bytes:
                        return template_bytes

                time.sleep(0.2)

            raise TimeoutError("หมดเวลารอสแกนลายนิ้วมือ กรุณาวางนิ้วแล้วลองอีกครั้ง")

        except TimeoutError:
            # No finger is a normal scan-cycle timeout, not a USB disconnection.
            raise
        except Exception as exc:
            last_error = exc

            set_scanner_status(
                False,
                0,
                "Scanner disconnected or unavailable"
            )
            app.logger.warning(
                "Scanner init/capture failed; retrying in %.1f seconds (%s: %s)",
                retry_interval,
                type(exc).__name__,
                exc,
            )
        finally:
            # Cleanup must never prevent the reconnect loop from continuing.
            if zkfp is not None and device_opened:
                try:
                    zkfp.CloseDevice()
                except Exception as cleanup_error:
                    app.logger.debug("CloseDevice during recovery: %s", cleanup_error)

            if zkfp is not None and sdk_initialized:
                try:
                    zkfp.Terminate()
                except Exception as cleanup_error:
                    app.logger.debug("Terminate during recovery: %s", cleanup_error)

        remaining = reconnect_deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(retry_interval, remaining))
    set_scanner_status(
        False,
        0,
        "Scanner is disconnected"
    )
    raise ConnectionError(
        "ไม่สามารถเชื่อมต่อเครื่องสแกน ZK9500 ได้ "
        "กรุณาตรวจสอบสาย USB ระบบจะลองเชื่อมต่อใหม่ในรอบถัดไป"
    ) from last_error


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


@app.before_request
def authenticate_scanner_request():
    global LOCAL_SESSION_TOKEN, LOCAL_SESSION_EXPIRES
    if not request.path.startswith("/api/scanner/"):
        return None

    if request.method == "OPTIONS":
        return None

    # Only accept loopback Host headers to reduce DNS-rebinding exposure.
    host = (request.host or "").split(":", 1)[0].lower()
    if host not in {"127.0.0.1", "localhost"}:
        return jsonify({"success": False, "message": "Invalid local host"}), 403

    origin = request.headers.get("Origin", "")
    if origin and origin not in FRONTEND_ORIGINS:
        return jsonify({"success": False, "message": "Origin not allowed"}), 403

    if request.path == "/api/scanner/pair" and request.method == "POST":
        return None

    if not LOCAL_SESSION_TOKEN or time.time() >= LOCAL_SESSION_EXPIRES:
        LOCAL_SESSION_TOKEN = None
        return jsonify({"success": False, "message": "Scanner is not paired. Please pair this computer first."}), 401

    supplied = request.headers.get("X-Scanner-Session", "")
    if not hmac.compare_digest(supplied, LOCAL_SESSION_TOKEN):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    return None


@app.post("/api/scanner/pair")
def scanner_pair():
    global LOCAL_SESSION_TOKEN, LOCAL_SESSION_EXPIRES
    if not LOCAL_PAIRING_CODE:
        return jsonify({"success": False, "message": "LOCAL_PAIRING_CODE is not configured"}), 503
    payload = request.get_json(silent=True) or {}
    supplied = str(payload.get("code", ""))
    if not hmac.compare_digest(supplied, LOCAL_PAIRING_CODE):
        return jsonify({"success": False, "message": "Invalid pairing code"}), 401
    LOCAL_SESSION_TOKEN = secrets.token_urlsafe(32)
    LOCAL_SESSION_EXPIRES = time.time() + LOCAL_SESSION_TTL
    return jsonify({"success": True, "token": LOCAL_SESSION_TOKEN,
                    "expires_in": LOCAL_SESSION_TTL}), 200


@app.post("/api/scanner/unpair")
def scanner_unpair():
    global LOCAL_SESSION_TOKEN, LOCAL_SESSION_EXPIRES
    LOCAL_SESSION_TOKEN = None
    LOCAL_SESSION_EXPIRES = 0
    enrollment.update({"active": False, "user_id": None, "templates": []})
    return jsonify({"success": True, "message": "Scanner unpaired"}), 200

@app.get("/api/scanner/health")
def scanner_health():
    return jsonify({
        "success": True,
        **scanner_status
    }), 200

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
    """Capture and identify fingerprint, then record attendance."""
    try:
        headers = cloud_headers()

        # 1. Load fingerprint templates BEFORE acquiring scanner_lock.
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
            return jsonify({
                "success": False,
                "message": templates_data.get("message") or
                    f"โหลดข้อมูลลายนิ้วมือไม่สำเร็จ "
                    f"(HTTP {templates_response.status_code})"
            }), 502

        enrolled_templates = templates_data.get("templates", [])

        if not enrolled_templates:
            return jsonify({
                "success": False,
                "message": "ยังไม่มีผู้ใช้ลงทะเบียนลายนิ้วมือ"
            }), 404

        # 2. Acquire the lock only while using the scanner SDK.
        with scanner_lock:
            captured = capture_fingerprint(timeout=30)

            matched = identify_fingerprint(
                captured,
                enrolled_templates
            )

        if not matched:
            return jsonify({
                "success": False,
                "matched": False,
                "message": "ไม่พบลายนิ้วมือในระบบ กรุณาลองอีกครั้ง"
            }), 404

        # 3. Record attendance AFTER releasing scanner_lock.
        record_response = requests.post(
            f"{CLOUD_API_URL}/api/checkin/record",
            json={
                "fingerprint_id": matched["fingerprint_id"]
            },
            headers=headers,
            timeout=30
        )

        try:
            record_data = record_response.json()
        except ValueError:
            record_data = {}

        if not record_response.ok:
            return jsonify({
                "success": False,
                "section_mismatch": record_data.get(
                    "section_mismatch", False
                ),
                "message": record_data.get("message") or
                    f"บันทึกเวลาเข้าเรียนไม่สำเร็จ "
                    f"(HTTP {record_response.status_code})"
            }), record_response.status_code

        return jsonify({
            "success": True,
            "matched": True,
            "score": matched.get("score"),
            "user": record_data.get("user"),
            "attendance": record_data.get("attendance"),
            "message": record_data.get(
                "message", "เช็คชื่อสำเร็จ"
            )
        }), 200

    except TimeoutError as exc:
        return jsonify({
            "success": False,
            "message": str(exc)
        }), 408

    except ConnectionError as exc:
        app.logger.warning(
            "Fingerprint scanner is disconnected: %s",
            exc
        )

        return jsonify({
            "success": False,
            "scanner_connected": False,
            "message": str(exc)
        }), 503

    except requests.RequestException:
        app.logger.exception(
            "Cloud API request failed during check-in"
        )

        return jsonify({
            "success": False,
            "message": "ไม่สามารถเชื่อมต่อ Cloud API ได้"
        }), 502

    except Exception as exc:
        app.logger.exception("Fingerprint check-in failed")

        return jsonify({
            "success": False,
            "message": str(exc)
        }), 500

@app.post("/api/scanner/enroll/cancel")
def enroll_cancel():
    with scanner_lock:
        enrollment.update({"active": False, "user_id": None, "templates": []})
    return jsonify({"success": True, "message": "ยกเลิกการลงทะเบียนแล้ว"}), 200


if __name__ == "__main__":
    # Loopback only: the scanner must not be exposed to the LAN.
    app.run(host="127.0.0.1", port=5001, debug=False, threaded=True)
