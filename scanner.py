"""
ZKTeco ZK9500 USB Fingerprint Scanner
Project: fingerprint-attendance

ลงทะเบียนลายนิ้วมือ:
    python scanner.py --enroll

สแกนเช็กชื่อ:
    python scanner.py

หยุดโปรแกรม:
    Ctrl+C
"""

import argparse
import base64
import json
import os
import time
import traceback
from datetime import datetime
from pathlib import Path

import requests
from pyzkfp import ZKFP2


# =========================
# Configuration
# =========================

API_URL = "http://127.0.0.1:5000/api/scan"

ENROLL_NEXT_URL = "http://127.0.0.1:5000/api/scanner/enrollment/next"
ENROLL_RESULT_URL = "http://127.0.0.1:5000/api/scanner/enrollment/result"
TEMPLATE_FILE = "fingerprint_templates.json"

CAPTURE_DELAY = 0.25
CAPTURE_SIZE = 2048
DUPLICATE_DELAY = 3


# =========================
# ZK9500 Scanner
# =========================

class ZK9500Scanner:

    def __init__(self):
        self.zk = ZKFP2()
        self.initialized = False
        self.opened = False

    def connect(self):
        """Initialize SDK and open the fingerprint scanner."""

        print("กำลังเริ่มต้น SDK...")

        self.zk.Init()
        self.initialized = True

        print("เริ่มต้น SDK สำเร็จ")

        count = self.zk.GetDeviceCount()
        print(f"พบอุปกรณ์: {count}")

        if not count:
            raise RuntimeError(
                "ไม่พบเครื่องสแกน กรุณาตรวจสอบ USB และ Driver"
            )

        print("กำลังเปิดเครื่อง ZK9500...")

        self.zk.OpenDevice(0)
        self.opened = True

        print("เชื่อมต่อเครื่องสแกนสำเร็จ")

    def capture(self):
        """Capture a fingerprint using the installed pyzkfp API."""
        while True:
            result = self.zk.AcquireFingerprint()

            if result is not None:
                if isinstance(result, (tuple, list)) and len(result) >= 2:
                    template, _image = result

                    if template:
                        return bytes(template)

            time.sleep(CAPTURE_DELAY)

    def disconnect(self):
        """Close device and terminate SDK safely."""

        if self.opened:
            try:
                self.zk.CloseDevice()
                print("ปิดเครื่องสแกนแล้ว")
            except Exception as exc:
                print(f"ปิดเครื่องสแกนไม่สำเร็จ: {exc}")
            finally:
                self.opened = False

        if self.initialized:
            try:
                self.zk.Terminate()
                print("ปิด SDK แล้ว")
            except Exception as exc:
                print(f"ปิด SDK ไม่สำเร็จ: {exc}")
            finally:
                self.initialized = False


# =========================
# Local fingerprint storage
# =========================

def load_templates():
    """Load registered fingerprint templates from JSON."""

    if not TEMPLATE_FILE.exists():
        return {}

    try:
        with TEMPLATE_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError(
                "fingerprint_templates.json ต้องเป็น JSON object"
            )

        return data

    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(
            f"อ่านไฟล์ template ไม่สำเร็จ: {exc}"
        ) from exc


def save_templates(templates):
    """Save templates to JSON."""

    with TEMPLATE_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            templates,
            file,
            ensure_ascii=False,
            indent=2
        )


def load_templates_into_sdk(scanner, templates):
    """Load all registered templates into the SDK memory."""

    loaded = 0

    for fingerprint_id, encoded in templates.items():
        try:
            fid = int(fingerprint_id)
            template = base64.b64decode(
                encoded,
                validate=True
            )

            scanner.zk.DBAdd(fid, template)
            loaded += 1

        except Exception as exc:
            print(
                f"[WARN] โหลด template รหัส "
                f"{fingerprint_id} ไม่สำเร็จ: {exc}"
            )

    print(
        f"โหลด template เข้า SDK แล้ว "
        f"{loaded}/{len(templates)} รายการ"
    )

    return loaded


# =========================
# Enroll fingerprint
# =========================

def enroll(scanner):
    """Enroll the same finger three times."""

    templates = load_templates()

    fingerprint_id = input(
        "กำหนด fingerprint_id เช่น 1001: "
    ).strip()

    if not fingerprint_id.isdigit():
        print("fingerprint_id ต้องเป็นตัวเลข เช่น 1001")
        return

    fid = int(fingerprint_id)

    if fid < 0:
        print("fingerprint_id ต้องไม่ติดลบ")
        return

    if fingerprint_id in templates:
        confirm = input(
            "รหัสนี้มี template แล้ว ต้องการลงทะเบียนทับหรือไม่? (y/N): "
        ).strip().lower()

        if confirm != "y":
            print("ยกเลิกการลงทะเบียน")
            return
    captures = []

    for index in range(3):
        input(
            f"ครั้งที่ {index + 1}/3: "
            "วางนิ้วบนเครื่องแล้วกด Enter..."
        )

        print("กำลังอ่านลายนิ้วมือ...")

        template = scanner.capture()

        if not template:
            print("ไม่พบ template กรุณาลองใหม่")
            return

        captures.append(template)

        print("อ่านลายนิ้วมือสำเร็จ กรุณานำนิ้วออก")
        time.sleep(1)

    print("กำลังรวม template...")

    merged, merged_length = scanner.zk.DBMerge(
        captures[0],
        captures[1],
        captures[2]
    )

    if not merged:
        print("รวม template ไม่สำเร็จ กรุณาลงทะเบียนใหม่")
        return

    merged = bytes(merged)

    if merged_length and len(merged) != int(merged_length):
        print(
            "คำเตือน: ความยาว template ไม่ตรงกับค่าที่ SDK คืนมา"
        )

    if fingerprint_id in templates:
        try:
            scanner.zk.DBDel(fid)
        except Exception as exc:
            print(
                f"[WARN] ลบ template เก่าใน SDK ไม่สำเร็จ: {exc}"
            )

    scanner.zk.DBAdd(fid, merged)
    templates[fingerprint_id] = base64.b64encode(
        merged
    ).decode("ascii")

    save_templates(templates)

    print(f"ลงทะเบียนลายนิ้วมือรหัส {fingerprint_id} สำเร็จ")
    print("เพิ่มหรือแก้ไขผู้ใช้ในหน้าเว็บให้ใช้ fingerprint_id เดียวกัน")


def send_scan(fingerprint_id):
    """Send a recognized fingerprint ID to the Flask API."""

    payload = {
        "fingerprint_id": str(fingerprint_id),
        "scanned_at": datetime.now().astimezone().isoformat(
            timespec="seconds"
        ),
    }

    try:
        response = requests.post(
            API_URL,
            json=payload,
            timeout=5
        )

        response.raise_for_status()
        data = response.json()

        if data.get("status") == "matched":
            print(
                f"[MATCH] {data.get('full_name')} "
                f"({data.get('student_id')}) "
                f"เวลา {data.get('scanned_at')}"
            )
        else:
            print(
                f"[UNMATCHED] ไม่พบผู้ใช้ "
                f"fingerprint_id={fingerprint_id}"
            )

    except requests.RequestException as exc:
        print(f"[ERROR] ส่งข้อมูลไป Flask ไม่สำเร็จ: {exc}")

    except ValueError as exc:
        print(f"[ERROR] Flask ตอบกลับไม่ใช่ JSON: {exc}")




def get_enrollment_job():
    try:
        response = requests.get(ENROLL_NEXT_URL, timeout=2)
        response.raise_for_status()
        data = response.json()

        if data.get("job_id"):
            return data

    except requests.RequestException as exc:
        print(f"[WARN] ติดต่อ API งานลงทะเบียนไม่ได้: {exc}")

    return None


def send_enrollment_result(job_id, success, message):
    try:
        response = requests.post(
            ENROLL_RESULT_URL,
            json={
                "job_id": job_id,
                "success": success,
                "message": message
            },
            timeout=5
        )
        response.raise_for_status()

    except requests.RequestException as exc:
        print(f"[ERROR] ส่งผลลงทะเบียนไม่ได้: {exc}")


def process_enrollment(scanner, job):
    fingerprint_id = str(job["fingerprint_id"])
    job_id = job["job_id"]

    try:
        if not fingerprint_id.isdigit():
            raise ValueError("รหัสลายนิ้วมือต้องเป็นตัวเลข")

        fid = int(fingerprint_id)
        templates = load_templates()

        if fingerprint_id in templates:
            raise ValueError("รหัสนี้มี Template อยู่แล้ว")

        print(f"\nเริ่มลงทะเบียนรหัส {fingerprint_id}")
        captures = []

        for index in range(3):
            print(f"วางนิ้วครั้งที่ {index + 1}/3")

            template = scanner.capture()

            if not template:
                raise RuntimeError("อ่านลายนิ้วมือไม่สำเร็จ")

            captures.append(template)
            print("อ่านสำเร็จ กรุณานำนิ้วออก")
            time.sleep(1)

        merged, merged_length = scanner.zk.DBMerge(
            captures[0],
            captures[1],
            captures[2]
        )

        if not merged:
            raise RuntimeError("รวม Template ไม่สำเร็จ")

        merged = bytes(merged)

        # บันทึก Template เข้า SDK และไฟล์ในเครื่อง
        scanner.zk.DBAdd(fid, merged)

        templates[fingerprint_id] = base64.b64encode(
            merged
        ).decode("ascii")

        save_templates(templates)

        send_enrollment_result(
            job_id,
            True,
            "ลงทะเบียนลายนิ้วมือสำเร็จ"
        )

        print(f"[ENROLL] ลงทะเบียน {fingerprint_id} สำเร็จ")

    except Exception as exc:
        print(f"[ENROLL ERROR] {exc}")

        send_enrollment_result(
            job_id,
            False,
            str(exc)
        )


def scan_loop(scanner):
    """Identify fingerprints and send attendance events."""

    templates = load_templates()

    if not templates:
        print(
            "ยังไม่มีลายนิ้วมือที่ลงทะเบียน "
            "กรุณารัน python scanner.py --enroll"
        )
        return

    loaded = load_templates_into_sdk(scanner, templates)

    if loaded == 0:
        print("ไม่มี template ที่โหลดเข้า SDK สำเร็จ")
        return

    print("พร้อมสแกนเช็กชื่อ กด Ctrl+C เพื่อหยุด")

    last_id = None
    last_time = 0.0

    while True:
        job = get_enrollment_job()

        if job:
            process_enrollment(scanner, job)
            templates = load_templates()
            load_templates_into_sdk(scanner, templates)

            print("กลับเข้าสู่โหมดสแกนเช็กชื่อ")

        result = scanner.zk.AcquireFingerprint()

        if result is None:
            time.sleep(CAPTURE_DELAY)
            continue

        try:
            if not isinstance(result, (tuple, list)) or len(result) < 2:
                print("รูปแบบผลลัพธ์การสแกนไม่ถูกต้อง")
                time.sleep(CAPTURE_DELAY)
                continue

            template, _image = result

            if not template:
                time.sleep(CAPTURE_DELAY)
                continue

            uid, score = scanner.zk.DBIdentify(bytes(template))

            if uid is None or int(uid) < 0:
                print("ไม่พบลายนิ้วมือที่ลงทะเบียน")
                time.sleep(CAPTURE_DELAY)
                continue

            fingerprint_id = str(uid)
            now = time.time()

            # Avoid repeatedly logging the same finger
            # while it remains on the sensor.
            if (
                fingerprint_id != last_id
                or now - last_time >= DUPLICATE_DELAY
            ):
                print(
                    f"พบลายนิ้วมือรหัส {fingerprint_id} "
                    f"(score={score})"
                )

                send_scan(fingerprint_id)

                last_id = fingerprint_id
                last_time = now

            time.sleep(1)

        except Exception as exc:
            print(f"[ERROR] ระบุลายนิ้วมือไม่สำเร็จ: {exc}")
            traceback.print_exc()
            time.sleep(CAPTURE_DELAY)

def delete_fingerprint_template(fingerprint_id):
    if not os.path.exists(TEMPLATE_FILE):
        return

    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        templates = json.load(f)

    fingerprint_id = str(fingerprint_id)

    if fingerprint_id in templates:
        del templates[fingerprint_id]

        with open(TEMPLATE_FILE, "w", encoding="utf-8") as f:
            json.dump(
                templates,
                f,
                ensure_ascii=False,
                indent=2
            )

def main():
    parser = argparse.ArgumentParser(
        description="ZKTeco ZK9500 attendance scanner"
    )

    parser.add_argument(
        "--enroll",
        action="store_true",
        help="ลงทะเบียนลายนิ้วมือ"
    )

    args = parser.parse_args()
    scanner = ZK9500Scanner()

    try:
        scanner.connect()

        if args.enroll:
            enroll(scanner)
        else:
            scan_loop(scanner)

    except KeyboardInterrupt:
        print("\nหยุดโปรแกรม")

    except Exception as exc:
        print(f"[ERROR] {exc}")
        traceback.print_exc()

    finally:
        scanner.disconnect()


if __name__ == "__main__":
    main()
