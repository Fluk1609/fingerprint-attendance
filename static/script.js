// รีเฟรชรายการสแกนล่าสุดทุก 5 วินาที โดยไม่ต้องโหลดหน้าใหม่ทั้งหมด
async function refreshScans() {
  try {
    const res = await fetch("/api/scans/recent");
    const logs = await res.json();
    const tbody = document.querySelector("#scan-table tbody");
    if (!tbody) return;

    if (logs.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" class="empty">ยังไม่มีรายการสแกน</td></tr>`;
      return;
    }

    tbody.innerHTML = logs.map(log => {
      const statusHtml = log.status === "matched"
        ? `<span class="tag ok">พบข้อมูล</span>`
        : `<span class="tag warn">ไม่พบผู้ใช้ (${log.fingerprint_id ?? ""})</span>`;

      return `<tr>
        <td>${log.scanned_at ?? "-"}</td>
        <td>${log.student_id ?? "-"}</td>
        <td>${log.full_name ?? "-"}</td>
        <td>${log.department ?? "-"}</td>
        <td>${statusHtml}</td>
      </tr>`;
    }).join("");
  } catch (err) {
    console.error("ไม่สามารถดึงข้อมูลล่าสุดได้:", err);
  }
}

setInterval(refreshScans, 5000);
