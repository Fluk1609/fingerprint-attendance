# ระบบเช็คชื่อด้วยลายนิ้วมือ (มหาวิทยาลัย)

เว็บแอป Flask (รันผ่าน ASGI/uvicorn) + ฐานข้อมูล **Supabase** บันทึกวันเวลาที่สแกนลายนิ้วมือ
ผ่านเครื่อง **ZKTeco** พร้อมวัดชีพจร (ถ้ามีเซนเซอร์) และออกรายงานสรุปเป็น Excel

## โครงสร้างไฟล์

```
├── app.py               # เว็บแอป Flask (หน้าเว็บ + API) / asgi_app สำหรับ uvicorn
├── database.py          # ติดต่อ Supabase (users, scan_logs)
├── report.py            # สร้างไฟล์ Excel สรุปผล
├── scanner.py           # อ่านลายนิ้วมือจากเครื่อง ZKTeco (+ชีพจร) แล้วส่งเข้า /api/scan
├── zkteco_enroll.py     # ลงทะเบียนลายนิ้วมือผู้ใช้ใหม่ (วางนิ้วจริง 3 ครั้ง)
├── supabase_schema.sql  # SQL สร้าง/อัปเดตตาราง รันใน Supabase SQL Editor
├── test-superbase.py    # ทดสอบการเชื่อมต่อ Supabase
├── requirements.txt
└── templates/  static/
```

## ตั้งค่าครั้งแรก

1. **Supabase**: Dashboard > SQL Editor แล้วรันไฟล์ `supabase_schema.sql`
   (ปลอดภัยถ้ามีตารางอยู่แล้ว — จะเพิ่มเฉพาะ `users.fingerprint_template` และ `scan_logs.heart_rate`)
2. สร้างไฟล์ `.env`
   ```
   SUPABASE_URL=https://xxxx.supabase.co
   SUPABASE_KEY=<key ที่มีสิทธิ์เขียนตาราง>
   ```
   หมายเหตุ: `database.py` อ่าน `SUPABASE_KEY` แต่ `test-superbase.py` อ่าน `SUPABASE_PUBLISHABLE_KEY`
   ถ้าเปิด RLS ไว้ ต้องใช้ key ที่เขียนได้ หรือตั้ง policy ให้ตารางทั้งสอง
3. ติดตั้ง
   ```bash
   python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
4. เครื่อง ZKTeco: ติดตั้ง **ZKFinger SDK** จาก zkteco.com ก่อน (เป็นไดรเวอร์)
   และบน Linux/macOS ต้องมี .NET/Mono

## วิธีใช้งาน

```bash
python zkteco_enroll.py                                   # 1) ลงทะเบียนคน (ทีละคน)
uvicorn app:asgi_app --host 0.0.0.0 --port 5000 --reload   # 2) รันเว็บ -> http://127.0.0.1:5000
python scanner.py                                         # 3) รันตัวอ่านเครื่องสแกน
```

- `scanner.py` ตอนเริ่มจะโหลดเทมเพลตลายนิ้วมือทุกคนจาก Supabase เข้าความจำเครื่อง
  (เครื่องล้างความจำตอนปิด/ถอดสาย) ถ้าลงทะเบียนคนใหม่ระหว่างที่รันอยู่ ให้ปิดแล้วเปิดใหม่
- ทดสอบโดยไม่มีเครื่องจริง: ใน `main()` ของ `scanner.py` เปลี่ยน `ZKTecoScanner()` เป็น `MockScanner()`

## ชีพจร

เครื่องสแกนลายนิ้วมือวัดชีพจรเองไม่ได้ ต้องมีเซนเซอร์ PPG แยก (เช่น MAX30102) ตอนนี้ใช้ `MockHeartRateSensor`
(สุ่ม 60-100 bpm) เมื่อมีฮาร์ดแวร์จริงให้เขียน class สืบทอด `HeartRateSensor` ใน `scanner.py`
(มีตัวอย่าง MAX30102 ในคอมเมนต์) แล้วแก้บรรทัดใน `main()`

## หมายเหตุ

- เปลี่ยน `app.secret_key` ใน `app.py` ก่อนใช้งานจริง และอย่า commit `.env`
- ลายนิ้วมือเป็นข้อมูลชีวมิติ ควรตรวจนโยบาย PDPA และจำกัดสิทธิ์ตาราง `users.fingerprint_template`
- ยังไม่มีระบบ login สำหรับหน้า "จัดการผู้ใช้" และ "รายงาน"
