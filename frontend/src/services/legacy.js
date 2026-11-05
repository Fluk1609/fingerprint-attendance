
export function formatScanDate(value) {
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

export function getThaiDateString(value) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return "";

  const thaiDate = new Date(date.getTime() + 7 * 60 * 60 * 1000);

  const year = thaiDate.getUTCFullYear();
  const month = String(thaiDate.getUTCMonth() + 1).padStart(2, "0");
  const day = String(thaiDate.getUTCDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
}

export function getTodayThaiDateString() {
  const now = new Date();
  const thaiNow = new Date(now.getTime() + 7 * 60 * 60 * 1000);

  const year = thaiNow.getUTCFullYear();
  const month = String(thaiNow.getUTCMonth() + 1).padStart(2, "0");
  const day = String(thaiNow.getUTCDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
}
