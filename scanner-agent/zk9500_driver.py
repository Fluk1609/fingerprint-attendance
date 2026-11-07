
import time
from pyzkfp import ZKFP2


CAPTURE_DELAY = 0.25


class ZK9500Scanner:
    def __init__(self):
        self.zk = ZKFP2()
        self.initialized = False
        self.opened = False

    def connect(self):
        print("กำลังเริ่มต้น ZKFinger SDK...")

        self.zk.Init()
        self.initialized = True

        count = self.zk.GetDeviceCount()
        print(f"พบอุปกรณ์สแกน: {count}")

        if not count:
            raise RuntimeError(
                "ไม่พบเครื่อง ZK9500 กรุณาตรวจสอบ USB และ Driver"
            )

        self.zk.OpenDevice(0)
        self.opened = True

        print("เชื่อมต่อ ZK9500 สำเร็จ")

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
            finally:
                self.opened = False

        if self.initialized:
            try:
                self.zk.Terminate()
                print("ปิด SDK แล้ว")
            finally:
                self.initialized = False
