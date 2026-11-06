from pyzkfp import ZKFP2
import time

zkfp = ZKFP2()

sdk_initialized = False
device_opened = False
db_initialized = False

FINGERPRINT_ID = 1
templates = []

try:
    # 1. Initialize SDK
    print("กำลังเริ่มต้น SDK...")
    zkfp.Init()
    sdk_initialized = True

    # 2. Open scanner
    print("กำลังเปิดเครื่องสแกน...")
    zkfp.OpenDevice(0)
    device_opened = True

    # 3. Initialize fingerprint database
    print("กำลังสร้าง Fingerprint Database...")
    db_handle = zkfp.DBInit()
    db_initialized = True

    print("Database พร้อมใช้งาน")
    print("DB Handle:", db_handle)

    # 4. Capture fingerprint 3 times
    for i in range(3):
        print(f"\n========== SCAN {i + 1}/3 ==========")

        if i > 0:
            input("กรุณายกนิ้วออกจากเครื่อง แล้วกด Enter เพื่อสแกนอีกครั้ง...")

        print("กรุณาวางนิ้วบนเครื่องสแกน...")

        while True:
            result = zkfp.AcquireFingerprint()

            if result:
                template, image = result

                template_bytes = bytes(template)

                if len(template_bytes) == 0:
                    print("Template ว่าง กรุณาสแกนใหม่")
                    continue

                templates.append(template_bytes)

                print("สแกนสำเร็จ!")
                print("Template size:", len(template_bytes))
                break

            time.sleep(0.2)

    # 5. Merge 3 templates
    print("\nกำลังรวม Fingerprint Templates...")

    reg_template, reg_template_len = zkfp.DBMerge(
        templates[0],
        templates[1],
        templates[2]
    )

    registered_template = bytes(reg_template)

    print("Merge สำเร็จ!")
    print("Registered Template size:", len(registered_template))
    print("Template length:", reg_template_len)

    # 6. Add registered template to database
    print("\nกำลังบันทึก Fingerprint ลง Database...")

    zkfp.DBAdd(FINGERPRINT_ID, registered_template)

    print("Enroll สำเร็จ!")
    print("Fingerprint ID:", FINGERPRINT_ID)

    # 7. Identify fingerprint
    print("\nกำลังทดสอบ Fingerprint Identification...")

    fid, score = zkfp.DBIdentify(templates[0])

    print("Identified Fingerprint ID:", fid)
    print("Match Score:", score)

    if fid == FINGERPRINT_ID:
        print("\nSUCCESS: Fingerprint verification passed!")
    else:
        print("\nWARNING: Fingerprint was not identified.")

    # 8. Save registered template for testing
    with open("registered_fingerprint.bin", "wb") as f:
        f.write(registered_template)

    print("\nบันทึก registered_fingerprint.bin สำเร็จ")

except KeyboardInterrupt:
    print("\nยกเลิกการทำงาน")

except Exception as e:
    print("\nเกิดข้อผิดพลาด:", repr(e))

finally:
    if db_initialized:
        try:
            zkfp.DBFree()
            print("Database released")
        except Exception as e:
            print("DBFree error:", e)

    if device_opened:
        try:
            zkfp.CloseDevice()
            print("Device closed")
        except Exception as e:
            print("CloseDevice error:", e)

    if sdk_initialized:
        try:
            zkfp.Terminate()
            print("SDK terminated")
        except Exception as e:
            print("Terminate error:", e)

    print("สิ้นสุดการทดสอบ")
