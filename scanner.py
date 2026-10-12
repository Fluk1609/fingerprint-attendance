"""
scanner.py
----------
สคริปต์นี้รันแยกต่างหากบน "เครื่องที่ต่อเครื่องสแกนลายนิ้วมือ" (เครื่องเดียวกับที่รันเว็บก็ได้
เพราะโจทย์ระบุว่าเป็นระบบจุดเดียว) ทำหน้าที่:

  1. เชื่อมต่อกับเครื่องสแกนลายนิ้วมือผ่าน SDK ของยี่ห้อนั้นๆ
  2. เมื่อมีคนสแกนนิ้ว -> ได้ "fingerprint_id" ที่ตรงกับลายนิ้วมือที่เคยลงทะเบียนไว้
  3. (ถ้ามีเซนเซอร์วัดชีพจรต่อไว้) อ่านค่าชีพจรพร้อมกันในจังหวะเดียวกับตอนวางนิ้วสแกน
  4. ส่งข้อมูลไปยัง Flask API (POST /api/scan) เพื่อบันทึกวันเวลา (และชีพจรถ้ามี)

เครื่องสแกนที่ใช้งานจริง: ZKTeco (ซีรีส์ ZK เช่น ZK4500/ZK9500/ZK6500 หรือ SLK20R)
เชื่อมต่อผ่านไลบรารี pyzkfp (wrapper ของ ZKFinger SDK) ดู class ZKTecoScanner ด้านล่าง

ก่อนใช้งานเครื่องจริงต้อง:
  1. ติดตั้ง ZKFinger SDK ตัวจริงจากเว็บไซต์ ZKTeco (https://www.zkteco.com/en/Biometrics_Module_SDK)
     เพื่อให้ไดรเวอร์เครื่องทำงาน (จำเป็นแม้จะเรียกผ่าน pyzkfp)
  2. pip install pyzkfp
  3. บน Linux/macOS ต้องมี .NET หรือ Mono runtime ติดตั้งไว้ด้วย (Windows มีมาให้อยู่แล้ว)
  4. ลงทะเบียนลายนิ้วมือผู้ใช้แต่ละคนก่อน ด้วยสคริปต์ zkteco_enroll.py (แยกออกไปอีกไฟล์)

ตัวอย่างเซนเซอร์วัดชีพจรที่พบบ่อย (ยังไม่ทราบรุ่น จึงใช้ MockHeartRateSensor ไปก่อน ดูคอมเมนต์ท้ายไฟล์):
  - MAX30102 / MAX30100 (ต่อผ่าน I2C บน Raspberry Pi / ESP32) -> ไลบรารี max30102 หรือ smbus2
"""

import time
import random
import requests
from abc import ABC, abstractmethod

import database as db

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
# 1.1) ZKTecoScanner - เชื่อมต่อเครื่องสแกน ZKTeco จริงผ่าน pyzkfp
# ---------------------------------------------------------------------------
class ZKTecoScanner(FingerprintScanner):
    """
    เชื่อมต่อเครื่องสแกน ZKTeco (ซีรีส์ ZK เช่น ZK4500/ZK9500/ZK6500, SLK20R)
    ผ่านไลบรารี pyzkfp (pip install pyzkfp) ซึ่งเป็น wrapper ของ ZKFinger SDK

    วิธีทำงาน:
      - ตอน connect(): โหลดเทมเพลตลายนิ้วมือของผู้ใช้ทุกคนที่เคยลงทะเบียนไว้ (ผ่าน zkteco_enroll.py)
        จากฐานข้อมูล SQLite เข้าหน่วยความจำของตัวเครื่อง เพราะหน่วยความจำเครื่องจะถูกล้างทุกครั้ง
        ที่ปิดเครื่อง/ถอดสาย จึงต้องโหลดใหม่ทุกครั้งที่สคริปต์นี้เริ่มทำงาน
      - ตอน capture_and_identify(): อ่านลายนิ้วมือที่วางอยู่ แล้วเทียบกับฐานข้อมูลในเครื่อง (1:N)
        คืนค่า fingerprint_id (ตรงกับ users.id ในฐานข้อมูลเว็บ) ถ้าตรงกัน
    """

    MATCH_SCORE_THRESHOLD = 0  # pyzkfp: score 0 = ไม่ match, มากกว่า 0 = match (ปรับเพิ่มได้ถ้าอยากเข้มงวดขึ้น)

    def __init__(self):
        self.zkfp2 = None

    def connect(self):
        from pyzkfp import ZKFP2  # import ในนี้ เพื่อให้ไฟล์ยัง import ได้แม้ไม่ได้ติดตั้ง pyzkfp (เช่นตอนใช้ MockScanner)

        self.zkfp2 = ZKFP2()
        self.zkfp2.Init()

        device_count = self.zkfp2.GetDeviceCount()
        print(f"[ZKTecoScanner] พบเครื่องสแกน {device_count} เครื่อง")
        if device_count == 0:
            raise RuntimeError("ไม่พบเครื่องสแกนลายนิ้วมือ ZKTeco ที่เชื่อมต่ออยู่ ตรวจสอบสาย USB และไดรเวอร์ ZKFinger SDK")
        self.zkfp2.OpenDevice(0)

        # โหลดเทมเพลตของผู้ใช้ที่เคยลงทะเบียนไว้ทั้งหมดเข้าหน่วยความจำเครื่อง
        users = db.get_users_with_templates()
        for row in users:
            self.zkfp2.DBAdd(int(row["fingerprint_id"]), row["fingerprint_template"])
        print(f"[ZKTecoScanner] โหลดลายนิ้วมือที่เคยลงทะเบียนไว้แล้ว {len(users)} คนเข้าเครื่อง พร้อมใช้งาน")

    def capture_and_identify(self):
        capture = self.zkfp2.AcquireFingerprint()
        if not capture:
            return None  # ยังไม่มีคนวางนิ้ว หรืออ่านภาพไม่ชัด

        tmp, _img = capture
        finger_id, score = self.zkfp2.DBIdentify(tmp)
        if score > self.MATCH_SCORE_THRESHOLD:
            return str(finger_id)
        return None  # ลายนิ้วมือไม่ตรงกับที่ลงทะเบียนไว้ในเครื่อง

    def disconnect(self):
        if self.zkfp2:
            self.zkfp2.CloseDevice()
            self.zkfp2.Terminate()


# ---------------------------------------------------------------------------
# 2.1) Interface กลางสำหรับเซนเซอร์วัดชีพจร (แยกอิสระจากเซนเซอร์ลายนิ้วมือ)
# ---------------------------------------------------------------------------
class HeartRateSensor(ABC):
    @abstractmethod
    def connect(self):
        """เปิดการเชื่อมต่อกับเซนเซอร์วัดชีพจร"""
        raise NotImplementedError

    @abstractmethod
    def read_bpm(self):
        """
        อ่านค่าชีพจรปัจจุบัน (ครั้งต่อนาที, bpm) เป็น int
        คืนค่า None ถ้าอ่านค่าไม่สำเร็จ (เช่น วางนิ้ว/มือไม่สนิท หรือ timeout)
        """
        raise NotImplementedError

    @abstractmethod
    def disconnect(self):
        """ปิดการเชื่อมต่อกับเซนเซอร์"""
        raise NotImplementedError


class MockHeartRateSensor(HeartRateSensor):
    """เซนเซอร์จำลอง - สุ่มค่าชีพจรในช่วงปกติ (60-100 bpm) ใช้ทดสอบระบบโดยยังไม่ต้องมีฮาร์ดแวร์จริง"""

    def connect(self):
        print("[MockHeartRateSensor] เชื่อมต่อสำเร็จ (โหมดจำลอง)")

    def read_bpm(self):
        # จำลองเวลาที่เซนเซอร์ใช้อ่านค่าจริง (เซนเซอร์ PPG จริงมักใช้เวลาสองสามวินาที)
        time.sleep(1)
        bpm = random.randint(60, 100)
        print(f"[MockHeartRateSensor] อ่านค่าชีพจรได้ {bpm} bpm")
        return bpm

    def disconnect(self):
        print("[MockHeartRateSensor] ตัดการเชื่อมต่อ")


# ---------------------------------------------------------------------------
# 3) ตัวอย่างโครงสำหรับเซนเซอร์วัดชีพจร (ปิด comment ไว้ก่อน ให้แก้ตามรุ่นที่มีจริง)
# ---------------------------------------------------------------------------
#
# ตัวอย่างเซนเซอร์วัดชีพจร MAX30102 (ต่อผ่าน I2C บน Raspberry Pi)
# ติดตั้งไลบรารีตัวใดตัวหนึ่งที่รองรับบอร์ดของคุณ เช่น:
#   pip install max30102 smbus2   (หรือไลบรารีเฉพาะของผู้ผลิตบอร์ดที่ใช้)
#
# import max30102
# import hrcalc  # มักแถมมากับไลบรารี max30102 สำหรับคำนวณ bpm จากสัญญาณดิบ
#
# class Max30102HeartRateSensor(HeartRateSensor):
#     def __init__(self):
#         self.sensor = None
#
#     def connect(self):
#         self.sensor = max30102.MAX30102()
#
#     def read_bpm(self):
#         red, ir = self.sensor.read_sequential()
#         bpm_list, valid = hrcalc.calc_hr_and_spo2(ir, red)[:2]
#         if valid and bpm_list:
#             return int(bpm_list)
#         return None
#
#     def disconnect(self):
#         self.sensor.shutdown()


# ---------------------------------------------------------------------------
# ส่งผลสแกนไปยัง Flask API
# ---------------------------------------------------------------------------
def send_scan_to_server(fingerprint_id, heart_rate=None):
    try:
        response = requests.post(
            API_URL,
            json={"fingerprint_id": fingerprint_id, "heart_rate": heart_rate},
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()
        hr_text = f" | ชีพจร {heart_rate} bpm" if heart_rate else ""
        if data.get("status") == "matched":
            print(f"✅ บันทึกสำเร็จ: {data['full_name']} ({data['student_id']}) เวลา {data['scanned_at']}{hr_text}")
        else:
            print(f"⚠️  ไม่พบผู้ใช้ที่ลงทะเบียนลายนิ้วมือ '{fingerprint_id}' ในระบบ (บันทึกเป็น unmatched){hr_text}")
    except requests.exceptions.RequestException as exc:
        print(f"❌ ส่งข้อมูลไปเซิร์ฟเวอร์ไม่สำเร็จ: {exc}")


def main():
    # ใช้เครื่องสแกน ZKTeco จริง (เปลี่ยนเป็น MockScanner() ถ้าต้องการทดสอบระบบโดยยังไม่ต่อเครื่องจริง)
    scanner: FingerprintScanner = MockScanner()
    # ยังไม่ทราบรุ่นเซนเซอร์วัดชีพจร จึงใช้โหมดจำลองไปก่อน (เปลี่ยนเป็นคลาสจริงเมื่อทราบรุ่น เช่น Max30102HeartRateSensor)
    heart_rate_sensor: HeartRateSensor = MockHeartRateSensor()

    scanner.connect()
    heart_rate_sensor.connect()
    print("พร้อมสแกนลายนิ้วมือ (พร้อมวัดชีพจรไปด้วย) แล้ว... (กด Ctrl+C เพื่อออก)")
    try:
        while True:
            fingerprint_id = scanner.capture_and_identify()
            if fingerprint_id:
                # วัดชีพจรทันทีหลังจับนิ้วได้ ในจังหวะเดียวกับตอนวางนิ้วสแกน
                bpm = heart_rate_sensor.read_bpm()
                send_scan_to_server(fingerprint_id, heart_rate=bpm)
            # เครื่อง ZKTeco ต้อง poll ถี่ๆ เพื่อจับภาพได้ทันทีที่วางนิ้ว; MockScanner ไม่กระทบเพราะรอ input() อยู่แล้ว
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nกำลังปิดโปรแกรม...")
    finally:
        scanner.disconnect()
        heart_rate_sensor.disconnect()


if __name__ == "__main__":
    main()
