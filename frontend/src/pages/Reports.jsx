import { useCallback, useEffect, useMemo, useState } from "react";

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
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  const [startDate, setStartDate] = useState(toDisplayDate(today));
  const [endDate, setEndDate] = useState(toDisplayDate(today));
  const [selectedUserId, setSelectedUserId] = useState("");
  const [selectedSemesterId, setSelectedSemesterId] = useState("");
  const [users, setUsers] = useState([]);
  const [semesters, setSemesters] = useState([]);
  const [summary, setSummary] = useState([]);
  const [logs, setLogs] = useState([]);
  const [totals, setTotals] = useState({ total_scans: 0, on_time: 0, late: 0, unmatched: 0, people: 0 });
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState("");
  const [summarySearch, setSummarySearch] = useState("");
  const [logsSearch, setLogsSearch] = useState("");
  const [summaryPage, setSummaryPage] = useState(1);
  const [logsPage, setLogsPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  const fetchOptions = useCallback(async () => {
    try {
      const [ur, sr] = await Promise.all([
        fetch(`${API_BASE_URL}/api/users`, { cache: "no-store" }),
        fetch(`${API_BASE_URL}/api/semesters`, { cache: "no-store" }),
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
    const q = new URLSearchParams({ start_date: start, end_date: end });
    if (selectedUserId) q.set("user_id", selectedUserId);
    if (selectedSemesterId) q.set("semester_id", selectedSemesterId);
    return q;
  };
  const handleSearch = async (event) => {
    event.preventDefault();
    try {
      setLoading(true); setError("");
      const response = await fetch(`${API_BASE_URL}/api/reports?${queryParams()}`, { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.message || "ค้นหารายงานไม่สำเร็จ");
      setSummary(data.summary || []); setLogs(data.logs || []);
      setTotals(data.totals || { total_scans: 0, on_time: 0, late: 0, unmatched: 0, people: 0 });
    } catch (e) { setError(e.message); setSummary([]); setLogs([]); }
    finally { setLoading(false); }
  };
  const handleExport = async () => {
    try {
      setExporting(true); setError("");
      const response = await fetch(`${API_BASE_URL}/api/reports/export?${queryParams()}`);
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.message || "ดาวน์โหลดรายงานไม่สำเร็จ");
      }
      const blob = await response.blob(), url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url; link.download = `attendance_report_${toISODate(startDate)}_${toISODate(endDate)}.xlsx`;
      document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url);
    } catch (e) { setError(e.message); }
    finally { setExporting(false); }
  };
  const formatInput = setter => event => {
    const digits = event.target.value.replace(/\D/g, "").slice(0, 8);
    setter(digits.length > 4 ? `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}` : digits.length > 2 ? `${digits.slice(0, 2)}/${digits.slice(2)}` : digits);
  };
  const statusLabel = status => ({ on_time: "ตรงเวลา", late: "มาสาย", unmatched: "ไม่พบผู้ใช้", no_class: "ไม่มีวิชา" })[status] || status || "-";
  const filteredSummary = useMemo(() => summary.filter(x => `${x.student_id || ""} ${x.full_name || ""} ${x.department || ""}`.toLowerCase().includes(summarySearch.toLowerCase())), [summary, summarySearch]);
  const filteredLogs = useMemo(() => logs.filter(x => `${x.student_id || ""} ${x.full_name || ""} ${x.department || ""} ${x.subject_code || ""} ${x.subject_name || ""} ${statusLabel(x.status)}`.toLowerCase().includes(logsSearch.toLowerCase())), [logs, logsSearch]);
  const summaryPages = Math.max(1, Math.ceil(filteredSummary.length / pageSize));
  const logsPages = Math.max(1, Math.ceil(filteredLogs.length / pageSize));
  const pageSummary = filteredSummary.slice((summaryPage - 1) * pageSize, summaryPage * pageSize);
  const pageLogs = filteredLogs.slice((logsPage - 1) * pageSize, logsPage * pageSize);
  const attendanceRate = totals.total_scans ? Math.round((totals.on_time + totals.late) / totals.total_scans * 100) : 0;
  const chartTotal = Math.max(1, totals.on_time + totals.late + totals.unmatched);
  const printReport = () => window.print();

  return <>
    <div className="page-header"><h1>รายงานสรุปการเช็คชื่อ</h1><p className="hint">ค้นหา วิเคราะห์ และส่งออกรายงานการเข้าเรียน</p></div>
    <div className="card no-print">
      <h2>เงื่อนไขการค้นหา</h2>
      <form className="form-grid" onSubmit={handleSearch}>
        <div className="field"><label htmlFor="semester_id">ภาคเรียน</label><select id="semester_id" value={selectedSemesterId} onChange={e => setSelectedSemesterId(e.target.value)}><option value="">ทุกภาคเรียน</option>{semesters.map(x => <option key={x.id} value={x.id}>{x.semester_name}{x.is_active ? " (ปัจจุบัน)" : ""}</option>)}</select></div>
        <div className="field"><label htmlFor="start_date_display">วันที่เริ่มต้น</label><input id="start_date_display" value={startDate} onChange={formatInput(setStartDate)} placeholder="dd/mm/yyyy" inputMode="numeric" maxLength={10} required /></div>
        <div className="field"><label htmlFor="end_date_display">วันที่สิ้นสุด</label><input id="end_date_display" value={endDate} onChange={formatInput(setEndDate)} placeholder="dd/mm/yyyy" inputMode="numeric" maxLength={10} required /></div>
        <div className="field"><label htmlFor="user_id">เฉพาะบุคคล</label><select id="user_id" value={selectedUserId} onChange={e => setSelectedUserId(e.target.value)}><option value="">ทุกคน</option>{users.map(x => <option key={x.id} value={x.id}>{x.full_name} ({x.student_id})</option>)}</select></div>
        <div className="field submit button-container"><button type="submit" disabled={loading}>{loading ? "กำลังค้นหา..." : "ค้นหา"}</button><button type="button" className="btn-export" onClick={handleExport} disabled={exporting}>{exporting ? "กำลัง Export..." : "ดาวน์โหลด Excel (.xlsx)"}</button><button type="button" className="btn-secondary" onClick={printReport}>พิมพ์ / บันทึก PDF</button></div>
      </form>
      {error && <p className="flash error" role="alert">{error}</p>}
    </div>
    <div className="card">
      <h2>ภาพรวม</h2>
      <div className="dashboard-grid">
        {[
          { label: "รายการทั้งหมด", value: totals.total_scans, icon: "📋", color: "blue" },
          { label: "ตรงเวลา", value: totals.on_time, icon: "🟢", color: "green" },
          { label: "มาสาย", value: totals.late, icon: "⏰", color: "orange" },
          { label: "ไม่พบผู้ใช้", value: totals.unmatched, icon: "⚠️", color: "red" },
          { label: "จำนวนบุคคล", value: totals.people, icon: "👥", color: "purple" },
          { label: "สัดส่วนรายการที่พบผู้ใช้", value: `${attendanceRate}%`, icon: "📊", color: "teal" },
        ].map((item) => (
          <div className={`overview-card ${item.color}`} key={item.label}>
            <div className="overview-card-icon">{item.icon}</div>
            <div className="overview-card-content">
              <span>{item.label}</span>
              <strong>{item.value}</strong>
            </div>
          </div>
        ))}
      </div>
      <h3 style={{ marginTop: "1.5rem" }}>สัดส่วนสถานะการสแกน</h3>
      {[["ตรงเวลา", totals.on_time, "#16a34a"], ["มาสาย", totals.late, "#f59e0b"], ["ไม่พบผู้ใช้", totals.unmatched, "#ef4444"]].map(([label, value, color]) => <div key={label} style={{ display: "grid", gridTemplateColumns: "100px 1fr 55px", gap: 10, alignItems: "center", margin: "10px 0" }}><span>{label}</span><div style={{ height: 12, background: "#e5e7eb", borderRadius: 20, overflow: "hidden" }}><div style={{ height: "100%", width: `${Math.min(100, value / chartTotal * 100)}%`, background: color, borderRadius: 20 }} /></div><strong>{value}</strong></div>)}
      <p className="hint">เปอร์เซ็นต์นี้คำนวณจากรายการสแกนที่พบผู้ใช้เทียบกับรายการสแกนทั้งหมด ไม่ใช่อัตราการเข้าเรียนเทียบกับจำนวนครั้งที่มีเรียน</p></div>
    <div className="card"><h2>สรุปรายบุคคล ({filteredSummary.length})</h2><div className="form-grid no-print" style={{ marginBottom: 12 }}><div className="field"><label>ค้นหาบุคคล</label><input value={summarySearch} onChange={e => { setSummarySearch(e.target.value); setSummaryPage(1) }} placeholder="รหัส ชื่อ หรือหน่วยงาน" /></div><div className="field"><label>จำนวนรายการต่อหน้า</label><select value={pageSize} onChange={e => { setPageSize(Number(e.target.value)); setSummaryPage(1); setLogsPage(1) }}><option value={10}>10</option><option value={20}>20</option><option value={50}>50</option></select></div></div><div className="table-container"><table className="data-table">
      <thead><tr><th>รหัส</th><th>ชื่อ-นามสกุล</th><th>หน่วยงาน/สาขา</th><th>จำนวนครั้ง</th><th>ตรงเวลา</th><th>มาสาย</th><th>สแกนล่าสุด</th></tr></thead>
      <tbody>{loading ? <tr><td colSpan="7" className="empty">กำลังโหลดข้อมูล...</td></tr> : pageSummary.length ? pageSummary.map(x => <tr key={x.user_id ?? x.student_id}><td data-label="รหัส">{x.student_id}</td><td data-label="ชื่อ-นามสกุล">{x.full_name}</td><td data-label="หน่วยงาน/สาขา">{x.department || "-"}</td><td data-label="จำนวนครั้ง">{x.count}</td><td data-label="ตรงเวลา">{x.on_time_count}</td><td data-label="มาสาย">{x.late_count}</td><td data-label="สแกนล่าสุด">{formatDateTime(x.last)}</td></tr>) : <tr><td colSpan="7" className="empty">ไม่มีข้อมูลในเงื่อนไขที่เลือก</td></tr>}</tbody>
    </table></div><div className="no-print" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, marginTop: 12 }}><span className="hint">หน้า {summaryPage} / {summaryPages}</span><div style={{ display: "flex", gap: 8 }}><button type="button" className="btn-secondary" disabled={summaryPage <= 1} onClick={() => setSummaryPage(p => p - 1)}>ก่อนหน้า</button><button type="button" className="btn-secondary" disabled={summaryPage >= summaryPages} onClick={() => setSummaryPage(p => p + 1)}>ถัดไป</button></div></div></div>
    <div className="card"><h2>ประวัติรายการ ({filteredLogs.length})</h2><div className="field no-print" style={{ maxWidth: 420, marginBottom: 12 }}><label>ค้นหาประวัติ</label><input value={logsSearch} onChange={e => { setLogsSearch(e.target.value); setLogsPage(1) }} placeholder="รหัส ชื่อ รายวิชา หรือสถานะ" /></div><div className="table-container"><table className="data-table">
      <thead><tr><th>วันที่และเวลา</th><th>รหัส</th><th>ชื่อ-นามสกุล</th><th>หน่วยงาน/สาขา</th><th>รายวิชา</th><th>สถานะ</th></tr></thead>
      <tbody>{pageLogs.length ? pageLogs.map(x => <tr key={x.id}><td data-label="วันที่และเวลา">{formatDateTime(x.scanned_at)}</td><td data-label="รหัส">{x.student_id || "-"}</td><td data-label="ชื่อ-นามสกุล">{x.full_name || "-"}</td><td data-label="หน่วยงาน/สาขา">{x.department || "-"}</td><td data-label="รายวิชา">{x.subject_code || x.subject_name || "-"}</td><td data-label="สถานะ">{statusLabel(x.status)}</td></tr>) : <tr><td colSpan="6" className="empty">ไม่มีประวัติรายการ</td></tr>}</tbody>
    </table></div><div className="no-print" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, marginTop: 12 }}><span className="hint">หน้า {logsPage} / {logsPages}</span><div style={{ display: "flex", gap: 8 }}><button type="button" className="btn-secondary" disabled={logsPage <= 1} onClick={() => setLogsPage(p => p - 1)}>ก่อนหน้า</button><button type="button" className="btn-secondary" disabled={logsPage >= logsPages} onClick={() => setLogsPage(p => p + 1)}>ถัดไป</button></div></div></div>
    <style>{`@media print {.no-print{display:none!important} .card{break-inside:avoid;box-shadow:none!important;border:1px solid #ddd!important} body{background:#fff!important} .table-container{overflow:visible!important} table{font-size:10px!important}}`}</style>
  </>;
}
export default Reports;
