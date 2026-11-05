import { useCallback, useEffect, useState } from "react";

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || ""
).replace(/\/+$/, "");

function toISODate(displayDate) {
  if (!displayDate) return "";
  const parts = displayDate.split("/");
  if (parts.length !== 3) return "";
  const [day, month, year] = parts;
  if (!/^\d{2}$/.test(day) || !/^\d{2}$/.test(month) || !/^\d{4}$/.test(year)) return "";
  const d = new Date(Number(year), Number(month) - 1, Number(day));
  if (d.getFullYear() !== Number(year) || d.getMonth() !== Number(month) - 1 || d.getDate() !== Number(day)) return "";
  return `${year}-${month}-${day}`;
}
function toDisplayDate(value) {
  if (!value) return "";
  const [year, month, day] = value.split("-");
  return `${day}/${month}/${year}`;
}
function formatDateTime(value) {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "-";
  return new Intl.DateTimeFormat("th-TH", {
    timeZone: "Asia/Bangkok", dateStyle: "short", timeStyle: "short",
  }).format(d);
}
function Reports() {
  const now = new Date();
  const today = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}-${String(now.getDate()).padStart(2,"0")}`;
  const [startDate, setStartDate] = useState(toDisplayDate(today));
  const [endDate, setEndDate] = useState(toDisplayDate(today));
  const [selectedUserId, setSelectedUserId] = useState("");
  const [selectedSemesterId, setSelectedSemesterId] = useState("");
  const [users, setUsers] = useState([]);
  const [semesters, setSemesters] = useState([]);
  const [summary, setSummary] = useState([]);
  const [logs, setLogs] = useState([]);
  const [totals, setTotals] = useState({total_scans:0,on_time:0,late:0,unmatched:0,people:0});
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");

  const fetchOptions = useCallback(async () => {
    try {
      const [ur, sr] = await Promise.all([
        fetch(`${API_BASE_URL}/api/users`, {cache:"no-store"}),
        fetch(`${API_BASE_URL}/api/semesters`, {cache:"no-store"}),
      ]);
      if (!ur.ok || !sr.ok) throw new Error("ไม่สามารถโหลดตัวเลือกตัวกรองได้");
      const [u, s] = await Promise.all([ur.json(), sr.json()]);
      setUsers(Array.isArray(u) ? u : []);
      setSemesters(Array.isArray(s) ? s : []);
      const active = (Array.isArray(s) ? s : []).find(x => x.is_active);
      if (active) setSelectedSemesterId(String(active.id));
    } catch (e) { setError(e.message); }
  }, []);
  useEffect(() => { fetchOptions(); }, [fetchOptions]);

  const queryParams = () => {
    const start = toISODate(startDate), end = toISODate(endDate);
    if (!start || !end) throw new Error("กรุณาระบุวันที่ให้ถูกต้องในรูปแบบ dd/mm/yyyy");
    if (start > end) throw new Error("วันที่เริ่มต้นต้องไม่เกินวันที่สิ้นสุด");
    const q = new URLSearchParams({start_date:start,end_date:end});
    if (selectedUserId) q.set("user_id",selectedUserId);
    if (selectedSemesterId) q.set("semester_id",selectedSemesterId);
    return q;
  };
  const handleSearch = async (event) => {
    event.preventDefault();
    try {
      setLoading(true); setError("");
      const response = await fetch(`${API_BASE_URL}/api/reports?${queryParams()}`,{cache:"no-store"});
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || "ค้นหารายงานไม่สำเร็จ");
      setSummary(data.summary || []); setLogs(data.logs || []);
      setTotals(data.totals || {total_scans:0,on_time:0,late:0,unmatched:0,people:0});
    } catch(e) { setError(e.message); setSummary([]); setLogs([]); }
    finally { setLoading(false); }
  };
  const handleExport = async () => {
    try {
      setExporting(true); setError("");
      const response = await fetch(`${API_BASE_URL}/api/reports/export?${queryParams()}`);
      if (!response.ok) {
        const data = await response.json().catch(()=>({}));
        throw new Error(data.message || "ดาวน์โหลดรายงานไม่สำเร็จ");
      }
      const blob = await response.blob(), url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href=url; link.download=`attendance_report_${toISODate(startDate)}_${toISODate(endDate)}.xlsx`;
      document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url);
    } catch(e) { setError(e.message); }
    finally { setExporting(false); }
  };
  const formatInput = setter => event => {
    const digits=event.target.value.replace(/\D/g,"").slice(0,8);
    setter(digits.length>4?`${digits.slice(0,2)}/${digits.slice(2,4)}/${digits.slice(4)}`:digits.length>2?`${digits.slice(0,2)}/${digits.slice(2)}`:digits);
  };
  const statusLabel = status => ({on_time:"ตรงเวลา",late:"มาสาย",unmatched:"ไม่พบผู้ใช้",no_class:"ไม่มีวิชา"})[status] || status || "-";

  return <>
    <div className="page-header"><h1>รายงานสรุปการเช็คชื่อ</h1><p className="hint">ค้นหาและสรุปตามช่วงวันที่ ภาคเรียน และบุคคล</p></div>
    <div className="card">
      <h2>เงื่อนไขการค้นหา</h2>
      <form className="form-grid" onSubmit={handleSearch}>
        <div className="field"><label htmlFor="semester_id">ภาคเรียน</label><select id="semester_id" value={selectedSemesterId} onChange={e=>setSelectedSemesterId(e.target.value)}><option value="">ทุกภาคเรียน</option>{semesters.map(x=><option key={x.id} value={x.id}>{x.semester_name}{x.is_active?" (ปัจจุบัน)":""}</option>)}</select></div>
        <div className="field"><label htmlFor="start_date_display">วันที่เริ่มต้น</label><input id="start_date_display" value={startDate} onChange={formatInput(setStartDate)} placeholder="dd/mm/yyyy" inputMode="numeric" maxLength={10} required /></div>
        <div className="field"><label htmlFor="end_date_display">วันที่สิ้นสุด</label><input id="end_date_display" value={endDate} onChange={formatInput(setEndDate)} placeholder="dd/mm/yyyy" inputMode="numeric" maxLength={10} required /></div>
        <div className="field"><label htmlFor="user_id">เฉพาะบุคคล</label><select id="user_id" value={selectedUserId} onChange={e=>setSelectedUserId(e.target.value)}><option value="">ทุกคน</option>{users.map(x=><option key={x.id} value={x.id}>{x.full_name} ({x.student_id})</option>)}</select></div>
        <div className="field submit button-container"><button type="submit" disabled={loading}>{loading?"กำลังค้นหา...":"ค้นหา"}</button><button type="button" className="btn-export" onClick={handleExport} disabled={exporting}>{exporting?"กำลัง Export...":"ดาวน์โหลด Excel (.xlsx)"}</button></div>
      </form>
      {error && <p className="flash error" role="alert">{error}</p>}
    </div>
    <div className="card"><h2>ภาพรวม</h2><div className="dashboard-grid">
      {[
        ["รายการทั้งหมด",totals.total_scans],["ตรงเวลา",totals.on_time],["มาสาย",totals.late],["ไม่พบผู้ใช้",totals.unmatched],["จำนวนบุคคล",totals.people]
      ].map(([label,value])=><div className="stat-card" key={label}><span>{label}</span><strong>{value}</strong></div>)}
    </div></div>
    <div className="card"><h2>สรุปรายบุคคล ({summary.length})</h2><div className="table-container"><table className="data-table">
      <thead><tr><th>รหัส</th><th>ชื่อ-นามสกุล</th><th>หน่วยงาน/สาขา</th><th>จำนวนครั้ง</th><th>ตรงเวลา</th><th>มาสาย</th><th>สแกนล่าสุด</th></tr></thead>
      <tbody>{loading?<tr><td colSpan="7" className="empty">กำลังโหลดข้อมูล...</td></tr>:summary.length?summary.map(x=><tr key={x.user_id??x.student_id}><td>{x.student_id}</td><td>{x.full_name}</td><td>{x.department}</td><td>{x.count}</td><td>{x.on_time_count}</td><td>{x.late_count}</td><td>{formatDateTime(x.last)}</td></tr>):<tr><td colSpan="7" className="empty">ไม่มีข้อมูลในเงื่อนไขที่เลือก</td></tr>}</tbody>
    </table></div></div>
    <div className="card"><h2>ประวัติรายการ ({logs.length})</h2><div className="table-container"><table className="data-table">
      <thead><tr><th>วันที่และเวลา</th><th>รหัส</th><th>ชื่อ-นามสกุล</th><th>หน่วยงาน/สาขา</th><th>รายวิชา</th><th>สถานะ</th></tr></thead>
      <tbody>{logs.length?logs.map(x=><tr key={x.id}><td>{formatDateTime(x.scanned_at)}</td><td>{x.student_id||"-"}</td><td>{x.full_name||"-"}</td><td>{x.department||"-"}</td><td>{x.subject_code||x.subject_name||"-"}</td><td>{statusLabel(x.status)}</td></tr>):<tr><td colSpan="6" className="empty">ไม่มีประวัติรายการ</td></tr>}</tbody>
    </table></div></div>
  </>;
}
export default Reports;
