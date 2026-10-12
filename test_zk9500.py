
from pyzkfp import ZKFP2

zkfp = ZKFP2()

try:
    print("กำลังเริ่มต้น SDK...")
    zkfp.Init()
    print("เริ่มต้น SDK สำเร็จ")

    print("กำลังเปิดเครื่อง ZK9500...")
    zkfp.OpenDevice(0)
    print("เชื่อมต่อเครื่องสแกนสำเร็จ")

except Exception as e:
    print(f"เชื่อมต่อไม่สำเร็จ: {e}")

finally:
    try:
        zkfp.CloseDevice()
    except Exception:
        pass

    try:
        zkfp.Terminate()
    except Exception:
        pass

    print("ปิดการเชื่อมต่อแล้ว")
