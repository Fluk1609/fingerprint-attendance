from pyzkfp import ZKFP2
import time

zkfp = ZKFP2()

device_opened = False
sdk_initialized = False

try:
    print("กำลังเริ่มต้น SDK...")
    zkfp.Init()
    sdk_initialized = True

    print("กำลังเปิดเครื่องสแกน...")
    zkfp.OpenDevice(0)
    device_opened = True

    print("\nพร้อมสแกนลายนิ้วมือ")
    print("กรุณาวางนิ้วบนเครื่อง ZK9500")

    while True:
        result = zkfp.AcquireFingerprint()

        if result:
            template, image = result

            print("\nสแกนลายนิ้วมือสำเร็จ!")
            print("Template type:", type(template))
            print("Template size:", len(template))
            print("Image type:", type(image))
            print("Image size:", len(image))

            # บันทึก Template สำหรับทดสอบ
            with open("fingerprint_template.bin", "wb") as f:
                f.write(bytes(template))

            print("บันทึก fingerprint_template.bin สำเร็จ")
            break

        time.sleep(0.2)

except KeyboardInterrupt:
    print("\nยกเลิกการสแกน")

except Exception as e:
    print("เกิดข้อผิดพลาด:", e)

finally:
    if device_opened:
        zkfp.CloseDevice()

    if sdk_initialized:
        zkfp.Terminate()

    print("ปิดการเชื่อมต่อแล้ว")
