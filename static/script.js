function formatScanDate(value) {
  if (!value) return "-";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const thaiDate = new Date(date.getTime() + 7 * 60 * 60 * 1000);

  const day = String(thaiDate.getUTCDate()).padStart(2, "0");
  const month = String(thaiDate.getUTCMonth() + 1).padStart(2, "0");
  const year = thaiDate.getUTCFullYear();
  const hours = String(thaiDate.getUTCHours()).padStart(2, "0");
  const minutes = String(thaiDate.getUTCMinutes()).padStart(2, "0");

  return `${day}/${month}/${year} : ${hours}:${minutes}`;
}

function getThaiDateString(value) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "";

  const thaiDate = new Date(date.getTime() + 7 * 60 * 60 * 1000);

  const year = thaiDate.getUTCFullYear();
  const month = String(thaiDate.getUTCMonth() + 1).padStart(2, "0");
  const day = String(thaiDate.getUTCDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
}

function getTodayThaiDateString() {
  const now = new Date();
  const thaiNow = new Date(now.getTime() + 7 * 60 * 60 * 1000);

  const year = thaiNow.getUTCFullYear();
  const month = String(thaiNow.getUTCMonth() + 1).padStart(2, "0");
  const day = String(thaiNow.getUTCDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
}

async function refreshScans() {
  try {
    const res = await fetch("/api/scans/recent", {
      cache: "no-store"
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }

    const logs = await res.json();
    const tbody = document.querySelector("#scan-table tbody");
    if (!tbody) return;

    const today = getTodayThaiDateString();

    const todayLogs = logs.filter(log =>
      getThaiDateString(log.scanned_at) === today
    );

    if (!todayLogs.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6" class="empty">
            วันนี้ยังไม่มีรายการสแกน
          </td>
        </tr>`;
      return;
    }

    tbody.innerHTML = todayLogs.map(log => {
      const statusHtml = {
        late: '<span class="tag warn">มาสาย</span>',
        on_time: '<span class="tag ok">ตรงเวลา</span>',
        matched: '<span class="tag ok">พบข้อมูล</span>',
        no_class: '<span class="tag warn">ไม่มีวิชาในเวลานี้</span>',
        unmatched: `<span class="tag warn">ไม่พบผู้ใช้ (${log.fingerprint_id ?? ""})</span>`
      }[log.status] ?? `<span class="tag">${log.status ?? "-"}</span>`;

      return `
        <tr>
          <td>${formatScanDate(log.scanned_at)}</td>
          <td>${log.student_id ?? "-"}</td>
          <td>${log.full_name ?? "-"}</td>
          <td>${log.department ?? "-"}</td>
          <td>${log.subject_code ?? log.subject_name ?? "-"}</td>
          <td>${statusHtml}</td>
        </tr>`;
    }).join("");

  } catch (err) {
    console.error("ไม่สามารถดึงข้อมูลล่าสุดได้:", err);
  }
}

refreshScans();
setInterval(refreshScans, 5000);
