import argparse
import base64
import time
import traceback
from datetime import datetime

import requests
from pyzkfp import ZKFP2
import database as db

API_URL = "http://127.0.0.1:5000/api/scan"

ENROLL_NEXT_URL = "http://127.0.0.1:5000/api/scanner/enrollment/next"
ENROLL_RESULT_URL = "http://127.0.0.1:5000/api/scanner/enrollment/result"

CAPTURE_DELAY = 0.25
CAPTURE_SIZE = 2048
DUPLICATE_DELAY = 3

class ZK9500Scanner:

    def __init__(self):
        self.zk = ZKFP2()
        self.initialized = False
        self.opened = False

    def connect(self):
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
        while True:
            result = self.zk.AcquireFingerprint()

            if result is not None:
                if isinstance(result, (tuple, list)) and len(result) >= 2:
                    template, _image = result

                    if template:
                        return bytes(template)

            time.sleep(CAPTURE_DELAY)

    def disconnect(self):
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

def load_templates():
    return db.get_all_fingerprint_templates()


def load_templates_into_sdk(scanner, templates):
    loaded = 0

    for fingerprint_id, template in templates.items():
        try:
            fid = int(fingerprint_id)
            if isinstance(template, str):
                template = base64.b64decode(template, validate=True)
            try:
                scanner.zk.DBDel(fid)
            except Exception:
                pass

            scanner.zk.DBAdd(fid, bytes(template))
            loaded += 1

        except Exception as exc:
            print(
                f"[WARN] โหลด Template รหัส {fingerprint_id} ไม่สำเร็จ: {exc}"
            )

    print(
        f"โหลด Template จาก Supabase เข้า SDK แล้ว "
        f"{loaded}/{len(templates)} รายการ"
    )
    return loaded

def enroll(scanner):
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
    try:
        has_template = db.has_fingerprint_template(fingerprint_id)
    except Exception as exc:
        print(f"[ERROR] ตรวจสอบ Template ใน Supabase ไม่สำเร็จ: {exc}")
        return

    if has_template:
        confirm = input(
            "รหัสนี้มี Template แล้ว ต้องการลงทะเบียนทับหรือไม่? (y/N): "
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

        try:
            template = scanner.capture()
        except Exception as exc:
            print(f"[ERROR] อ่านลายนิ้วมือไม่สำเร็จ: {exc}")
            return

        if not template:
            print("ไม่พบ Template กรุณาลองใหม่")
            return

        captures.append(bytes(template))

        print("อ่านลายนิ้วมือสำเร็จ กรุณานำนิ้วออก")

        time.sleep(1)

    print("กำลังรวม Template...")

    try:
        merged, merged_length = scanner.zk.DBMerge(
            captures[0],
            captures[1],
            captures[2]
        )
    except Exception as exc:
        print(f"[ERROR] รวม Template ไม่สำเร็จ: {exc}")
        return

    if not merged:
        print("รวม Template ไม่สำเร็จ กรุณาลงทะเบียนใหม่")
        return

    merged = bytes(merged)

    if merged_length and len(merged) != int(merged_length):
        print(
            "คำเตือน: ความยาว Template ไม่ตรงกับค่าที่ SDK คืนมา"
        )

    try:
        db.update_fingerprint_template(
            fingerprint_id,
            merged
        )
    except Exception as exc:
        print(f"[ERROR] บันทึก Template ลง Supabase ไม่สำเร็จ: {exc}")
        return

    try:
        if has_template:
            try:
                scanner.zk.DBDel(fid)
            except Exception as exc:
                print(f"[WARN] ลบ Template เดิมใน SDK ไม่สำเร็จ: {exc}")
                print("Template ถูกบันทึกใน Supabase แล้ว กรุณาเริ่ม Scanner ใหม่")
                return

        scanner.zk.DBAdd(fid, merged)

    except Exception as exc:
        print(
            "[WARN] บันทึกลง Supabase สำเร็จ "
            f"แต่เพิ่ม Template เข้า SDK ไม่สำเร็จ: {exc}"
        )
        print("กรุณาโหลด Template ใหม่หรือเริ่ม Scanner ใหม่")
        return

    print(
        f"[SUCCESS] ลงทะเบียนลายนิ้วมือรหัส {fingerprint_id} สำเร็จ"
    )
    print("บันทึก Template ลง Supabase เรียบร้อย")

def send_scan(fingerprint_id):

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
    replace_existing = job.get("replace_existing") is True

    try:
        if not fingerprint_id.isdigit():
            raise ValueError("รหัสลายนิ้วมือต้องเป็นตัวเลข")

        fid = int(fingerprint_id)
        has_template = db.has_fingerprint_template(fingerprint_id)

        if has_template and not replace_existing:
            raise ValueError(
                "รหัสนี้มี Template อยู่แล้ว กรุณายืนยันการเปลี่ยนลายนิ้วมือก่อน"
            )

        old_template = (
            db.get_fingerprint_template(fingerprint_id)
            if has_template else None
        )

        print(f"\\nเริ่มลงทะเบียนรหัส {fingerprint_id}")
        captures = []

        for index in range(3):
            print(f"วางนิ้วครั้งที่ {index + 1}/3")
            template = scanner.capture()

            if not template:
                raise RuntimeError("อ่านลายนิ้วมือไม่สำเร็จ")

            captures.append(bytes(template))
            print("อ่านสำเร็จ กรุณานำนิ้วออก")
            time.sleep(1)

        merged, merged_length = scanner.zk.DBMerge(
            captures[0], captures[1], captures[2]
        )

        if not merged:
            raise RuntimeError("รวม Template ไม่สำเร็จ")

        merged = bytes(merged)

        if merged_length and len(merged) != int(merged_length):
            print("[WARN] ความยาว Template ไม่ตรงกับค่าที่ SDK คืนมา")

        sdk_changed = False
        try:
            if has_template:
                scanner.zk.DBDel(fid)

            scanner.zk.DBAdd(fid, merged)
            sdk_changed = True

            db.update_fingerprint_template(fingerprint_id, merged)

        except Exception:
            if sdk_changed:
                try:
                    scanner.zk.DBDel(fid)
                except Exception:
                    pass

            if has_template and old_template:
                try:
                    scanner.zk.DBAdd(fid, bytes(old_template))
                except Exception as restore_exc:
                    print(
                        "[CRITICAL] คืน Template เดิมเข้า SDK ไม่สำเร็จ: "
                        f"{restore_exc}"
                    )
            raise

        send_enrollment_result(
            job_id, True, "ลงทะเบียนลายนิ้วมือสำเร็จ"
        )
        print(f"[ENROLL] ลงทะเบียน {fingerprint_id} สำเร็จ")

    except Exception as exc:
        print(f"[ENROLL ERROR] {exc}")
        send_enrollment_result(job_id, False, str(exc))


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
    """Clear a user's stored fingerprint template in Supabase."""
    response = (
        db.supabase.table("users")
        .update({"fingerprint_template": None})
        .eq("fingerprint_id", str(fingerprint_id))
        .execute()
    )
    return response.data


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
