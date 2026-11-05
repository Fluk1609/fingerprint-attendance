
from pyzkfp import ZKFP2
import traceback


def main():
    scanner = ZKFP2()
    initialized = False
    opened = False

    try:
        print("กำลังเริ่มต้น ZKFinger SDK...")

        scanner.Init()
        initialized = True

        print("SDK initialized successfully")

        count = scanner.GetDeviceCount()
        print(f"พบอุปกรณ์สแกน: {count}")

        if count <= 0:
            print("ไม่พบเครื่องสแกน กรุณาตรวจสอบ USB และ Driver")
            return

        print("กำลังเปิดเครื่อง ZK9500...")

        scanner.OpenDevice(0)
        opened = True

        print("เชื่อมต่อ ZK9500 สำเร็จ!")

    except Exception as exc:
        print(f"เกิดข้อผิดพลาด: {exc}")
        traceback.print_exc()

    finally:
        if opened:
            try:
                scanner.CloseDevice()
                print("ปิดเครื่องสแกนแล้ว")
            except Exception as exc:
                print(f"ปิดเครื่องไม่สำเร็จ: {exc}")

        if initialized:
            try:
                scanner.Terminate()
                print("ปิด SDK แล้ว")
            except Exception as exc:
                print(f"ปิด SDK ไม่สำเร็จ: {exc}")


if __name__ == "__main__":
    main()
