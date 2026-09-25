"""
scanner.py
----------
สคริปต์นี้รันแยกต่างหากบน "เครื่องที่ต่อเครื่องสแกนลายนิ้วมือ" (เครื่องเดียวกับที่รันเว็บก็ได้
เพราะโจทย์ระบุว่าเป็นระบบจุดเดียว) ทำหน้าที่:

  1. เชื่อมต่อกับเครื่องสแกนลายนิ้วมือผ่าน SDK ของยี่ห้อนั้นๆ
  2. เมื่อมีคนสแกนนิ้ว -> ได้ "fingerprint_id" ที่ตรงกับลายนิ้วมือที่เคยลงทะเบียนไว้
  3. ส่งข้อมูลไปยัง Flask API (POST /api/scan) เพื่อบันทึกวันเวลา

เนื่องจากยังไม่ทราบยี่ห้อ/รุ่นเครื่องที่แน่ชัด ไฟล์นี้ทำเป็น "โครงกลาง" (adapter pattern)
คุณเพียงเขียน class ใหม่สืบทอดจาก FingerprintScanner แล้ว implement 3 เมธอด
(connect, capture_and_identify, disconnect) ให้ตรงกับ SDK จริงของเครื่องคุณ
ระบบเว็บ/ฐานข้อมูลทั้งหมดจะไม่ต้องแก้อะไรเลย

ตัวอย่าง SDK ที่พบบ่อย (ดูคอมเมนต์ท้ายไฟล์):
  - ZKTeco (ZK4500 / ZK9500)      -> ไลบรารี pyzkfp หรือ zkteco-python
  - DigitalPersona / HID          -> DigitalPersona SDK (ผ่าน ctypes เรียก dpfpdd.dll) หรือ digitalpersona-sdk
  - Suprema                        -> BioStar SDK / BioMini SDK
"""

import time
import random
import requests
from abc import ABC, abstractmethod

API_URL = "http://127.0.0.1:5000/api/scan"


# ---------------------------------------------------------------------------
# 1) Interface กลาง - ทุกยี่ห้อต้อง implement ให้ครบ 3 เมธอดนี้
# ---------------------------------------------------------------------------
class FingerprintScanner(ABC):
    @abstractmethod
    def connect(self):
        """เปิดการเชื่อมต่อกับอุปกรณ์"""
        raise NotImplementedError

    @abstractmethod
    def capture_and_identify(self):
        """
        รอจนกว่าจะมีคนวางนิ้ว แล้วคืนค่า fingerprint_id (str) ที่ตรงกับลายนิ้วมือ
        ที่เคยลงทะเบียนไว้ในตัวเครื่อง/ฐานข้อมูลของ SDK
        คืนค่า None ถ้าจับคู่ไม่สำเร็จ (ลายนิ้วมือไม่ตรงกับที่ลงทะเบียนไว้)
        """
        raise NotImplementedError

    @abstractmethod
    def disconnect(self):
        """ปิดการเชื่อมต่อกับอุปกรณ์"""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# 2) MockScanner - ใช้ทดสอบระบบทั้งหมดโดยยังไม่ต้องมีเครื่องจริง
#    (พิมพ์รหัสลายนิ้วมือจากคีย์บอร์ดแทนการวางนิ้วจริง)
# ---------------------------------------------------------------------------
class MockScanner(FingerprintScanner):
    def connect(self):
        print("[MockScanner] เชื่อมต่อสำเร็จ (โหมดจำลอง)")

    def capture_and_identify(self):
        print("\nพิมพ์ fingerprint_id เพื่อจำลองการสแกน (หรือกด Enter เฉยๆ เพื่อจำลองว่าสแกนไม่ผ่าน)")
        value = input(">> รหัสลายนิ้วมือ: ").strip()
        return value if value else None

    def disconnect(self):
        print("[MockScanner] ตัดการเชื่อมต่อ")


# ---------------------------------------------------------------------------
# 3) ตัวอย่างโครงสำหรับ SDK จริง (ปิด comment ไว้ก่อน ให้แก้ตามยี่ห้อจริง)
# ---------------------------------------------------------------------------
#
# ตัวอย่าง ZKTeco (ไลบรารี pyzkfp: pip install pyzkfp)
#
# from pyzkfp import ZKFP2
#
# class ZKTecoScanner(FingerprintScanner):
#     def __init__(self):
#         self.zkfp2 = ZKFP2()
#
#     def connect(self):
#         self.zkfp2.Init()
#         self.zkfp2.OpenDevice(0)
#         # โหลดเทมเพลตลายนิ้วมือที่เคยลงทะเบียนไว้ทั้งหมดเข้าเครื่อง
#         # self.zkfp2.DBAdd(fingerprint_id, template)  # ทำตอนลงทะเบียนผู้ใช้ใหม่
#
#     def capture_and_identify(self):
#         capture = self.zkfp2.AcquireFingerprint()
#         if capture:
#             tmp, img = capture
#             uid, score = self.zkfp2.DBIdentify(tmp)
#             return str(uid) if score > 0 else None
#         return None
#
#     def disconnect(self):
#         self.zkfp2.CloseDevice()
#         self.zkfp2.Terminate()
#
#
# ตัวอย่าง DigitalPersona (ผ่าน ctypes เรียก DLL ของ SDK, จะต่างกันตามเวอร์ชัน SDK)
#
# import ctypes
#
# class DigitalPersonaScanner(FingerprintScanner):
#     def __init__(self):
#         self.dll = ctypes.WinDLL("dpfpdd.dll")
#
#     def connect(self):
#         self.dll.dpfpdd_init()
#         # เปิดอุปกรณ์ตาม API ของ SDK ที่ติดตั้งจริง
#
#     def capture_and_identify(self):
#         # เรียก capture + matching ตาม API ของ SDK
#         # คืนค่า fingerprint_id ที่ match ได้
#         raise NotImplementedError
#
#     def disconnect(self):
#         self.dll.dpfpdd_exit()


# ---------------------------------------------------------------------------
# ส่งผลสแกนไปยัง Flask API
# ---------------------------------------------------------------------------
def send_scan_to_server(fingerprint_id):
    try:
        response = requests.post(
            API_URL,
            json={"fingerprint_id": fingerprint_id},
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "matched":
            print(f"✅ บันทึกสำเร็จ: {data['full_name']} ({data['student_id']}) เวลา {data['scanned_at']}")
        else:
            print(f"⚠️  ไม่พบผู้ใช้ที่ลงทะเบียนลายนิ้วมือ '{fingerprint_id}' ในระบบ (บันทึกเป็น unmatched)")
    except requests.exceptions.RequestException as exc:
        print(f"❌ ส่งข้อมูลไปเซิร์ฟเวอร์ไม่สำเร็จ: {exc}")


def main():
    # >>> เปลี่ยนบรรทัดนี้เป็นคลาสของ SDK จริงเมื่อทราบยี่ห้อ/รุ่นเครื่อง <<<
    scanner: FingerprintScanner = MockScanner()

    scanner.connect()
    print("พร้อมสแกนลายนิ้วมือแล้ว... (กด Ctrl+C เพื่อออก)")
    try:
        while True:
            fingerprint_id = scanner.capture_and_identify()
            if fingerprint_id:
                send_scan_to_server(fingerprint_id)
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nกำลังปิดโปรแกรม...")
    finally:
        scanner.disconnect()


if __name__ == "__main__":
    main()
