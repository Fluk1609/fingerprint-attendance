-- supabase_schema.sql
-- -------------------
-- รันไฟล์นี้ใน Supabase SQL Editor (Dashboard > SQL Editor > New query)
-- ใช้ได้ทั้งตอนสร้างตารางใหม่ และตอนอัปเดตตารางเดิมที่มีอยู่แล้ว (คำสั่งเป็น idempotent)

-- ตาราง users: ข้อมูลผู้ใช้งาน + ลายนิ้วมือที่ลงทะเบียนไว้
create table if not exists users (
    id bigint generated always as identity primary key,
    student_id text unique not null,
    full_name text not null,
    department text,
    fingerprint_id text unique,            -- รหัสอ้างอิงกับเครื่องสแกน (สำหรับ ZKTeco คือ id ของ users เอง)
    fingerprint_template text,             -- เทมเพลตลายนิ้วมือ (เข้ารหัส base64) โหลดกลับเข้าเครื่องทุกครั้งที่เปิดเครื่อง
    created_at timestamptz not null default now()
);

-- ตาราง scan_logs: ประวัติการสแกนทุกครั้ง
create table if not exists scan_logs (
    id bigint generated always as identity primary key,
    fingerprint_id text,
    user_id bigint references users (id) on delete set null,
    scanned_at timestamptz not null default now(),
    status text not null,                  -- 'matched' หรือ 'unmatched'
    heart_rate integer                     -- ชีพจรที่วัดได้พร้อมกันตอนสแกน (bpm) ถ้ามี
);

-- เผื่อ 2 ตารางนี้ถูกสร้างไว้ก่อนแล้วจากเวอร์ชันก่อนหน้า (ยังไม่มีคอลัมน์ใหม่)
alter table users add column if not exists fingerprint_template text;
alter table scan_logs add column if not exists heart_rate integer;

-- index ช่วยให้ค้นหา/กรองเร็วขึ้น
create index if not exists idx_scan_logs_scanned_at on scan_logs (scanned_at);
create index if not exists idx_scan_logs_user_id on scan_logs (user_id);
