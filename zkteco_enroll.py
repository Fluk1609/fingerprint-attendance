"""
zkteco_enroll.py
-----------------
สคริปต์ลงทะเบียนผู้ใช้ใหม่ด้วยเครื่องสแกน ZKTeco โดยตรง
รันบนเครื่องที่ต่อเครื่องสแกน ZKTeco อยู่ (เครื่องเดียวกับที่รัน scanner.py)
ใช้แทนการพิมพ์ "รหัสลายนิ้วมือ" เองในหน้าเว็บ "จัดการผู้ใช้" เพราะ ZKTeco ต้องวางนิ้วจริง

ขั้นตอนที่สคริปต์นี้ทำ:
  1. ถามข้อมูลผู้ใช้ (รหัสนักศึกษา/บุคลากร, ชื่อ-นามสกุล, หน่วยงาน)
  2. ให้วางนิ้วเดิมบนเครื่องสแกน 3 ครั้ง เพื่อเก็บเทมเพลตลายนิ้วมือ (ตามมาตรฐานของ ZKFinger SDK)
  3. รวม (merge) เทมเพลตทั้ง 3 เป็นเทมเพลตเดียว บันทึกลงฐานข้อมูล SQLite ของเว็บแอป
  4. โหลดเทมเพลตเข้าหน่วยความจำเครื่องสแกนทันที เพื่อให้เริ่มใช้งานได้เลยโดยไม่ต้องรอรีสตาร์ท scanner.py

หมายเหตุ: ผู้ใช้ที่ลงทะเบียนผ่านสคริปต์นี้จะไปปรากฏในหน้า "จัดการผู้ใช้" ของเว็บเหมือนเพิ่มผ่านฟอร์มปกติ
"""

import database as db

try:
    from pyzkfp import ZKFP2
except ImportError:
    ZKFP2 = None


def main():
    if ZKFP2 is None:
        print("ไม่พบไลบรารี pyzkfp กรุณาติดตั้งก่อน: pip install pyzkfp")
        print("และตรวจสอบว่าได้ติดตั้ง ZKFinger SDK ตัวจริงจากเว็บไซต์ ZKTeco แล้ว")
        return

    print("=== ลงทะเบียนผู้ใช้ใหม่ด้วยเครื่องสแกน ZKTeco ===")
    student_id = input("รหัสนักศึกษา/บุคลากร: ").strip()
    full_name = input("ชื่อ-นามสกุล: ").strip()
    department = input("หน่วยงาน/คณะ/สาขา: ").strip()

    if not student_id or not full_name:
        print("ต้องกรอกรหัสนักศึกษา/บุคลากร และชื่อ-นามสกุลให้ครบ")
        return

    db.init_db()  # เผื่อรันสคริปต์นี้เป็นครั้งแรกโดยยังไม่เคยรันเว็บแอปเลย

    try:
        user_id = db.create_user_placeholder(student_id, full_name, department)
    except Exception as exc:
        print(f"บันทึกข้อมูลผู้ใช้ไม่สำเร็จ (รหัสนักศึกษาอาจซ้ำ): {exc}")
        return

    print(f"สร้างข้อมูลผู้ใช้สำเร็จ (id={user_id}) กำลังเชื่อมต่อเครื่องสแกน...")

    zkfp2 = ZKFP2()
    zkfp2.Init()
    device_count = zkfp2.GetDeviceCount()
    if device_count == 0:
        print("ไม่พบเครื่องสแกนลายนิ้วมือ ZKTeco ที่เชื่อมต่ออยู่ ตรวจสอบสาย USB และไดรเวอร์")
        return
    zkfp2.OpenDevice(0)

    templates = []
    print("\nกรุณาวางนิ้วเดิมบนเครื่องสแกน 3 ครั้ง (ใช้นิ้วเดียวกันทุกครั้งเพื่อความแม่นยำ)")
    try:
        for i in range(3):
            print(f"-- ครั้งที่ {i + 1}/3: วางนิ้วบนเครื่องสแกน...")
            while True:
                capture = zkfp2.AcquireFingerprint()
                if capture:
                    tmp, _img = capture
                    templates.append(tmp)
                    print("   จับภาพสำเร็จ")
                    break

        reg_template, _reg_len = zkfp2.DBMerge(*templates)

        fingerprint_id = str(user_id)
        db.set_user_fingerprint(user_id, fingerprint_id, bytes(reg_template))
        zkfp2.DBAdd(user_id, reg_template)

        print(f"\n✅ ลงทะเบียน {full_name} ({student_id}) สำเร็จ พร้อมใช้งานได้ทันที")
        print("   (ถ้า scanner.py กำลังรันอยู่แล้ว ให้ปิดแล้วเปิดใหม่ เพื่อโหลดลายนิ้วมือล่าสุดเข้าเครื่อง)")

    finally:
        zkfp2.CloseDevice()
        zkfp2.Terminate()


if __name__ == "__main__":
    main()
