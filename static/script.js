function formatScanDate(value) {
  if (!value) return '-';

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }
  date.setUTCHours(date.getUTCHours() + 7);

  const day = String(date.getUTCDate()).padStart(2, '0');
  const month = String(date.getUTCMonth() + 1).padStart(2, '0');
  const year = date.getUTCFullYear();
  const hours = String(date.getUTCHours()).padStart(2, '0');
  const minutes = String(date.getUTCMinutes()).padStart(2, '0');

  return `${day}/${month}/${year} : ${hours}:${minutes}`;
}

async function refreshScans() {
  try {
    const res = await fetch("/api/scans/recent");
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }

    const logs = await res.json();
    const tbody = document.querySelector("#scan-table tbody");
    if (!tbody) return;

    if (!logs.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6" class="empty">ยังไม่มีรายการสแกน</td>
        </tr>`;
      return;
    }

    tbody.innerHTML = logs.map(log => {
      const statusHtml = {
        late: '<span class="tag warn">มาสาย</span>',
        on_time: '<span class="tag ok">ตรงเวลา</span>',
        matched: '<span class="tag ok">พบข้อมูล</span>',
        unmatched: `<span class="tag warn">ไม่พบผู้ใช้ (${log.fingerprint_id ?? ""})</span>`
      }[log.status] ?? `<span class="tag">${log.status ?? "-"}</span>`;

      return `
        <tr>
          <td>${formatScanDate(log.scanned_at)}</td>
          <td>${log.student_id ?? "-"}</td>
          <td>${log.full_name ?? "-"}</td>
          <td>${log.department ?? "-"}</td>
          <td>${log.subject_name ?? "-"}</td>
          <td>${statusHtml}</td>
        </tr>`;
    }).join("");
  } catch (err) {
    console.error("ไม่สามารถดึงข้อมูลล่าสุดได้:", err);
  }
}

refreshScans();
setInterval(refreshScans, 5000);