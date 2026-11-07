import { Link } from "react-router-dom";

const features = [
  {
    to: "/checkin",
    icon: "👆",
    title: "Fingerprint Check-in",
    description: "บันทึกเวลาเข้าเรียนด้วยการสแกนลายนิ้วมือ",
  },
  {
    to: "/users",
    icon: "👥",
    title: "User Management",
    description: "เพิ่ม แก้ไข และจัดการข้อมูลผู้ใช้งาน",
  },
  {
    to: "/sections",
    icon: "🏷️",
    title: "Section Management",
    description: "จัดการกลุ่มเรียนและสมาชิกในแต่ละกลุ่ม",
  },
  {
    to: "/subjects",
    icon: "📚",
    title: "Subject Management",
    description: "จัดการรายวิชาและกำหนดการเรียน",
  },
  {
    to: "/reports",
    icon: "📊",
    title: "Attendance Reports",
    description: "ตรวจสอบและดูรายงานประวัติการเข้าเรียน",
  },
  {
    to: "/semesters",
    icon: "🗓️",
    title: "Semester Management",
    description: "จัดการภาคเรียนและช่วงเวลาการศึกษา",
  },
];

function Home() {
  return (
    <div className="home-page">
      <section className="home-hero">
        <div className="home-hero-content">
          <span className="home-eyebrow">● SMART ATTENDANCE SYSTEM</span>
          <h1>Fingerprint<br />Attendance System</h1>
          <p>
            ระบบเช็คชื่อเข้าเรียนด้วยลายนิ้วมือ ช่วยให้การบันทึกเวลาเข้าเรียน
            เป็นเรื่องง่าย สะดวก และตรวจสอบข้อมูลได้จากที่เดียว
          </p>
          <div className="home-hero-actions">
            <Link to="/checkin" className="home-btn-primary">เริ่มเช็คชื่อ <span aria-hidden="true">→</span></Link>
            <Link to="/reports" className="home-btn-secondary">ดูรายงาน</Link>
          </div>
        </div>
        <div className="home-hero-art" aria-hidden="true">
          <div className="home-fingerprint-orbit">
            <img src="/images/fingerscan-icon-512.png" alt="" />
          </div>
        </div>
      </section>

      <div className="home-section-heading">
        <div>
          <h2>จัดการระบบ</h2>
          <p>เลือกเมนูที่ต้องการใช้งาน</p>
        </div>
      </div>

      <section className="home-feature-grid">
        {features.map((feature) => (
          <Link className="home-feature-card" to={feature.to} key={feature.to}>
            <span className="home-feature-icon" aria-hidden="true">{feature.icon}</span>
            <span>
              <h3>{feature.title}</h3>
              <p>{feature.description}</p>
            </span>
            <span className="home-feature-arrow" aria-hidden="true">›</span>
          </Link>
        ))}
      </section>

      <p className="home-footer-note">Fingerprint Attendance System · Smart, Simple, Secure</p>
    </div>
  );
}

export default Home;
