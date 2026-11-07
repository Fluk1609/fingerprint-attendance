const SCANNER_AGENT_URL = (
  import.meta.env.VITE_SCANNER_AGENT_URL || "http://127.0.0.1:5001"
).replace(/\/+$/, "");

const SESSION_KEY = "scanner_agent_session";

export function getScannerSession() {
  return sessionStorage.getItem(SESSION_KEY);
}

export function clearScannerSession() {
  sessionStorage.removeItem(SESSION_KEY);
}

async function parseResponse(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(
      data.message || `Scanner Agent ตอบกลับ HTTP ${response.status}`
    );
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data;
}

export async function scannerRequest(path, options = {}) {
  const token = getScannerSession();
  const headers = new Headers(options.headers || {});
  if (token) headers.set("X-Scanner-Session", token);
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${SCANNER_AGENT_URL}${path}`, {
    ...options,
    headers,
    cache: "no-store",
  });
  return parseResponse(response);
}

export async function pairScanner(code) {
  const response = await fetch(`${SCANNER_AGENT_URL}/api/scanner/pair`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
    cache: "no-store",
  });
  const data = await parseResponse(response);
  if (!data.token) throw new Error("Scanner Agent ไม่ได้ส่ง Session Token กลับมา");
  sessionStorage.setItem(SESSION_KEY, data.token);
  return data;
}

export async function unpairScanner() {
  try {
    await scannerRequest("/api/scanner/unpair", { method: "POST" });
  } finally {
    clearScannerSession();
  }
}

export function getScannerHealth() {
  return scannerRequest("/api/scanner/health");
}

export function getScannerAgentUrl() {
  return SCANNER_AGENT_URL;
}


/**
 * Clear a previous enrollment session and immediately start a new one.
 * Used only after the user confirms the restart prompt.
 */
export async function restartEnrollment(userId) {
  await scannerRequest("/api/scanner/enroll/cancel", {
    method: "POST",
  });

  return scannerRequest("/api/scanner/enroll/start", {
    method: "POST",
    body: JSON.stringify({ user_id: userId }),
  });
}
