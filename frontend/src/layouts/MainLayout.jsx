import { useCallback, useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import {
  clearScannerSession,
  getScannerHealth,
  getScannerAgentUrl,
  getScannerSession,
  pairScanner,
  unpairScanner,
} from "../services/scanner-agent.service";

function MainLayout() {
  const [pairingCode, setPairingCode] = useState("");
  const [scannerState, setScannerState] = useState("checking");
  const [scannerMessage, setScannerMessage] = useState("กำลังตรวจสอบ Scanner Agent...");
  const [deviceCount, setDeviceCount] = useState(0);
  const [busy, setBusy] = useState(false);

  const checkScanner = useCallback(async () => {
    if (!getScannerSession()) {
      setScannerState("unpaired");
      setScannerMessage("ยังไม่ได้ Pair เครื่องนี้");
      setDeviceCount(0);
      return;
    }
    try {
      const result = await getScannerHealth();
      setScannerState(result.connected ? "connected" : "disconnected");
      setScannerMessage(result.message || (result.connected ? "Scanner is ready" : "ไม่พบเครื่องสแกน"));
      setDeviceCount(result.device_count || 0);
    } catch (error) {
      if (error.status === 401) clearScannerSession();
      setScannerState(error.status === 401 ? "unpaired" : "offline");
      setScannerMessage(error.status === 401
        ? "Session หมดอายุ กรุณา Pair ใหม่"
        : error.message || "ไม่สามารถเชื่อมต่อ Scanner Agent ได้");
      setDeviceCount(0);
    }
  }, []);

  useEffect(() => {
    checkScanner();
    const timer = window.setInterval(checkScanner, 10000);
    return () => window.clearInterval(timer);
  }, [checkScanner]);

  const handlePair = async (event) => {
    event.preventDefault();
    if (!pairingCode.trim()) {
      setScannerMessage("กรุณากรอก Pairing Code");
      return;
    }
    setBusy(true);
    try {
      await pairScanner(pairingCode.trim());
      setPairingCode("");
      await checkScanner();
    } catch (error) {
      setScannerState("unpaired");
      setScannerMessage(error.message || "Pair เครื่องไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  };

  const handleUnpair = async () => {
    setBusy(true);
    try {
      await unpairScanner();
      setScannerState("unpaired");
      setScannerMessage("ยกเลิกการ Pair แล้ว");
      setDeviceCount(0);
    } catch (error) {
      setScannerMessage(error.message || "ยกเลิก Pair ไม่สำเร็จ");
    } finally {
      setBusy(false);
    }
  };

  const statusColor = scannerState === "connected" ? "#15803d"
    : scannerState === "checking" ? "#64748b" : "#b45309";

  return (
    <>
      <header className="topbar">
        <div className="brand">ระบบสแกนลายนิ้วมือ</div>
        <nav>
          <NavLink to="/" end>เช็คชื่อ</NavLink>
          <NavLink to="/users">ผู้ใช้งาน</NavLink>
          <NavLink to="/sections">กลุ่มเรียน</NavLink>
          <NavLink to="/subjects">วิชา</NavLink>
          <NavLink to="/reports">รายงาน</NavLink>
          <NavLink to="/semesters">จัดการภาคเรียน</NavLink>
        </nav>
      </header>

      <main className="container">
        <section
          className="card"
          style={{ marginBottom: "1rem", padding: "1rem" }}
          aria-label="สถานะเครื่องสแกนลายนิ้วมือ"
        >
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <strong>Scanner Agent</strong>
              <div style={{ color: statusColor, fontWeight: 600, marginTop: 4 }} role="status">
                ● {scannerMessage}
                {scannerState === "connected" ? ` (พบอุปกรณ์ ${deviceCount} เครื่อง)` : ""}
              </div>
              {/* <small style={{ color: "#64748b" }}>Local endpoint: {getScannerAgentUrl()}</small> */}
            </div>
            <button type="button" onClick={checkScanner} disabled={busy}>
              ตรวจสอบอีกครั้ง
            </button>
          </div>

          {scannerState !== "connected" ? (
            <form onSubmit={handlePair} style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginTop: "1rem" }}>
              <input
                type="password"
                value={pairingCode}
                onChange={(event) => setPairingCode(event.target.value)}
                placeholder="กรุณากรอกรหัสก่อนเริ่มใช้งาน"
                aria-label="Pairing Code"
                autoComplete="off"
                style={{ flex: "1 1 220px", minWidth: 0 }}
              />
              <button type="submit" disabled={busy || !pairingCode.trim()}>
                {busy ? "กำลังดำเนินการ..." : "Pair เครื่องนี้"}
              </button>
            </form>
          ) : (
            <div style={{ marginTop: "0.75rem" }}>
              <button type="button" onClick={handleUnpair} disabled={busy}>
                ยกเลิก Pair
              </button>
            </div>
          )}
        </section>

        <Outlet />
      </main>
    </>
  );
}

export default MainLayout;
