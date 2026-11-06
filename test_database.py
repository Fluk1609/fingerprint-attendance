from pyzkfp import ZKFP2

zkfp = ZKFP2()

try:
    print("กำลังเริ่มต้น SDK...")
    zkfp.Init()

    print("กำลังเปิดเครื่องสแกน...")
    zkfp.OpenDevice(0)

    print("กำลังสร้าง Fingerprint Database...")
    db_handle = zkfp.DBInit()

    print("DB Handle:", db_handle)
    print("Database initialization successful!")

    zkfp.DBFree()

except Exception as e:
    print("เกิดข้อผิดพลาด:", e)

finally:
    try:
        zkfp.CloseDevice()
    except:
        pass

    try:
        zkfp.Terminate()
    except:
        pass

    print("ปิดการเชื่อมต่อแล้ว")
