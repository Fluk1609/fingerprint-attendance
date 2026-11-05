import { NavLink, Outlet } from "react-router-dom";

function MainLayout() {
  return (
    <>
      <header className="topbar">
        <div className="brand">ระบบสแกนลายนิ้วมือ</div>

        <nav>
          <NavLink to="/" end>
            เช็คชื่อ
          </NavLink>

          <NavLink to="/users">
            ผู้ใช้งาน
          </NavLink>

          <NavLink to="/sections">
            กลุ่มเรียน
          </NavLink>

          <NavLink to="/subjects">
            วิชา
          </NavLink>

          <NavLink to="/reports">
            รายงาน
          </NavLink>

          <NavLink to="/semesters">
            จัดการภาคเรียน
          </NavLink>
        </nav>
      </header>

      <main className="container">
        <Outlet />
      </main>
    </>
  );
}

export default MainLayout;