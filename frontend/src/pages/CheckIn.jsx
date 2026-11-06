import { useEffect, useState } from "react";

import {
    formatScanDate,
    getThaiDateString,
    getTodayThaiDateString,
} from "../services/legacy";

const API_BASE_URL = (
    import.meta.env.VITE_API_BASE_URL || ""
).replace(/\/+$/, "");

const SCANNER_BASE_URL = "http://127.0.0.1:5001";


function CheckIn() {
    const [currentSubject, setCurrentSubject] = useState(null);
    const [currentSemester, setCurrentSemester] = useState(null);

    const [scans, setScans] = useState([]);

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    const [scanning, setScanning] = useState(false);
    const [scanMessage, setScanMessage] = useState("");
    const [scanDialog, setScanDialog] = useState(null);

    // =========================================
    // Format Semester Date
    // =========================================

    const formatSemesterDate = (value) => {
        if (!value) return "-";

        const [year, month, day] = value
            .split("-")
            .map(Number);

        if (!year || !month || !day) return "-";

        return new Date(
            year,
            month - 1,
            day
        ).toLocaleDateString("th-TH", {
            day: "2-digit",
            month: "short",
            year: "numeric"
        });
    };

    // =========================================
    // Fetch Data
    // =========================================

    useEffect(() => {
        let isMounted = true;

        const refreshScans = async () => {
            try {
                const [
                    scanResponse,
                    subjectResponse,
                    semesterResponse
                ] = await Promise.all([
                    fetch(
                        `${API_BASE_URL}/api/scans/recent`,
                        { cache: "no-store" }
                    ),

                    fetch(
                        `${API_BASE_URL}/api/current-subject`,
                        { cache: "no-store" }
                    ),

                    fetch(
                        `${API_BASE_URL}/api/checkin/semester`,
                        { cache: "no-store" }
                    )
                ]);

                if (!scanResponse.ok) {
                    throw new Error(
                        `Scan API HTTP ${scanResponse.status}`
                    );
                }

                if (!subjectResponse.ok) {
                    throw new Error(
                        `Subject API HTTP ${subjectResponse.status}`
                    );
                }

                if (!semesterResponse.ok) {
                    throw new Error(
                        `Semester API HTTP ${semesterResponse.status}`
                    );
                }

                const [
                    logs,
                    subject,
                    semesterData
                ] = await Promise.all([
                    scanResponse.json(),
                    subjectResponse.json(),
                    semesterResponse.json()
                ]);

                if (!isMounted) return;

                // กรองรายการสแกนของวันนี้
                const today = getTodayThaiDateString();

                const todayLogs = (Array.isArray(logs) ? logs : [])
                    .filter(
                        (log) =>
                            getThaiDateString(log.scanned_at) === today
                    );

                setScans(todayLogs);

                setCurrentSubject(subject);

                setCurrentSemester(
                    semesterData.active
                        ? semesterData.semester
                        : null
                );

                setError("");

            } catch (err) {
                console.error(
                    "ไม่สามารถดึงข้อมูลล่าสุดได้:",
                    err
                );

                if (isMounted) {
                    setError(
                        "ไม่สามารถโหลดข้อมูลล่าสุดได้"
                    );
                }

            } finally {
                if (isMounted) {
                    setLoading(false);
                }
            }
        };

        refreshScans();

        const intervalId = setInterval(
            refreshScans,
            5000
        );

        return () => {
            isMounted = false;
            clearInterval(intervalId);
        };

    }, []);

    // =========================================
    // Automatic Fingerprint Check-in
    // Scan continuously only while a subject is active.
    // =========================================

    useEffect(() => {
        if (!currentSubject?.active) {
            setScanning(false);
            setScanMessage("ขณะนี้ไม่มีรายวิชาที่กำลังเรียน จึงปิดการสแกนลายนิ้วมือ");
            setScanDialog(null);
            return;
        }

        let cancelled = false;
        let waitingTimer = null;

        const wait = (ms) => new Promise((resolve) => {
            waitingTimer = setTimeout(resolve, ms);
        });

        const refreshTodayScans = async () => {
            try {
                const response = await fetch(
                    `${API_BASE_URL}/api/scans/recent`,
                    { cache: "no-store" }
                );
                if (!response.ok) return;

                const logs = await response.json();
                const today = getTodayThaiDateString();

                if (!cancelled) {
                    setScans((Array.isArray(logs) ? logs : []).filter(
                        (log) => getThaiDateString(log.scanned_at) === today
                    ));
                }
            } catch (err) {
                console.error("Unable to refresh scan logs:", err);
            }
        };

        const scanContinuously = async () => {
            setScanning(true);
            setScanMessage("กำลังรอวางนิ้วบนเครื่องสแกน ZK9500...");

            while (!cancelled) {
                try {
                    const response = await fetch(
                        `${SCANNER_BASE_URL}/api/scanner/checkin`,
                        {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                        }
                    );

                    const data = await response.json().catch(() => ({}));

                    if (cancelled) break;

                    // HTTP 408 means no fingerprint was placed before timeout.
                    // Keep waiting for the next scan without showing an error popup.
                    if (response.status === 408) {
                        setScanMessage("กำลังรอวางนิ้วบนเครื่องสแกน...");
                        continue;
                    }

                    if (response.ok && data.success) {
                        const user = data.user || {};
                        const attendance = data.attendance || {};

                        setScanDialog({
                            success: true,
                            title: data.already_checked_in ? "เช็คชื่อแล้ว" : "เช็คชื่อสำเร็จ",
                            message: data.message || "บันทึกเวลาเข้าเรียนเรียบร้อยแล้ว",
                            studentId: user.student_id,
                            fullName: user.full_name,
                            department: user.department,
                            status: attendance.status,
                            scannedAt: attendance.scanned_at,
                            subjectName: attendance.subject_name || currentSubject?.name,
                        });

                        setScanMessage("สแกนสำเร็จแล้ว พร้อมรับการสแกนคนถัดไป");
                        await refreshTodayScans();

                        // Brief pause before asking the scanner for the next finger.
                        await wait(1200);
                        continue;
                    }

                    // Unknown fingerprints should not stop the continuous scan loop.
                    if (response.status === 404) {
                        setScanMessage(data.message || "ไม่พบข้อมูลลายนิ้วมือ กรุณาลองอีกครั้ง");
                        await wait(1200);
                        continue;
                    }

                    setScanMessage(
                        data.message || `เครื่องสแกนตอบกลับ HTTP ${response.status}`
                    );
                    await wait(3000);
                } catch (err) {
                    if (cancelled) break;

                    console.error("Fingerprint check-in error:", err);
                    setScanMessage(
                        "ไม่สามารถเชื่อมต่อ Scanner Agent ได้ กรุณาตรวจสอบว่าเปิด scanner.py อยู่"
                    );
                    await wait(3000);
                }
            }

            if (!cancelled) {
                setScanning(false);
            }
        };

        scanContinuously();

        return () => {
            cancelled = true;
            if (waitingTimer) clearTimeout(waitingTimer);
            setScanning(false);
        };
    }, [
        currentSubject?.active,
        currentSubject?.code,
        currentSubject?.start_time,
        currentSubject?.end_time,
    ]);

    const formatAttendanceTime = (value) => {
        if (!value) return "-";
        return formatScanDate(value);
    };

    // =========================================
    // Get Scan Status
    // =========================================

    const getStatus = (status, fingerprintId) => {
        const statusMap = {
            late: {
                label: "มาสาย",
                className: "warn"
            },

            on_time: {
                label: "ตรงเวลา",
                className: "ok"
            },

            matched: {
                label: "พบข้อมูล",
                className: "ok"
            },

            no_class: {
                label: "ไม่มีวิชาในเวลานี้",
                className: "warn"
            },

            unmatched: {
                label: `ไม่พบผู้ใช้ (${fingerprintId ?? ""})`,
                className: "warn"
            }
        };

        const result = statusMap[status];

        return (
            <span className={`tag ${result?.className ?? ""}`}>
                {result?.label ?? status ?? "-"}
            </span>
        );
    };

    // =========================================
    // Render
    // =========================================

    return (
        <>
            <div className="page-header">
                <h1>รายการสแกนล่าสุด</h1>

                <span className="badge live">
                    ● อัปเดตอัตโนมัติทุก 5 วินาที
                </span>
            </div>

            {/* Automatic Fingerprint Scanner */}
            <div className="card" style={{ marginBottom: "1rem", padding: "1rem" }}>
                <h2 style={{ marginTop: 0 }}>เช็คชื่อด้วยลายนิ้วมือ</h2>

                {currentSubject?.active ? (
                    <>
                        <p className="hint">
                            ระบบเปิดเครื่องสแกนอัตโนมัติสำหรับวิชาที่กำลังเรียน
                            ไม่ต้องกดปุ่มเริ่มสแกน
                        </p>
                        <p
                            role="status"
                            style={{
                                color: scanning ? "#16a34a" : "#64748b",
                                fontWeight: 600,
                            }}
                        >
                            {scanning
                                ? "● เครื่องสแกนพร้อมใช้งาน"
                                : "กำลังเตรียมเครื่องสแกน..."}
                        </p>
                        <p className="hint">{scanMessage}</p>

                        {scanDialog && (
                            <div
                                style={{
                                    marginTop: "1rem",
                                    padding: "1rem",
                                    borderRadius: "10px",
                                    background: "#f0fdf4",
                                    border: "1px solid #bbf7d0",
                                }}
                                aria-live="polite"
                            >
                                <strong style={{ color: "#15803d" }}>
                                    {scanDialog.title}
                                </strong>
                                <p>{scanDialog.message}</p>
                                <p><strong>รหัส:</strong> {scanDialog.studentId ?? "-"}</p>
                                <p><strong>ชื่อ:</strong> {scanDialog.fullName ?? "-"}</p>
                                <p><strong>หน่วยงาน/สาขา:</strong> {scanDialog.department ?? "-"}</p>
                                <p><strong>วิชา:</strong> {scanDialog.subjectName ?? currentSubject?.name ?? "-"}</p>
                                <p>
                                    <strong>สถานะ:</strong>{" "}
                                    {scanDialog.status === "on_time" ? "ตรงเวลา"
                                        : scanDialog.status === "late" ? "มาสาย"
                                        : scanDialog.status === "no_class" ? "ไม่มีวิชาในเวลานี้"
                                        : scanDialog.status ?? "-"}
                                </p>
                                <p>
                                    <strong>เวลาสแกน:</strong>{" "}
                                    {formatAttendanceTime(scanDialog.scannedAt)}
                                </p>
                            </div>
                        )}
                    </>
                ) : (
                    <div
                        style={{
                            padding: "1rem",
                            borderRadius: "10px",
                            background: "#fff7ed",
                            border: "1px solid #fed7aa",
                        }}
                    >
                        <strong style={{ color: "#c2410c" }}>No Active Subject</strong>
                        <p className="hint" style={{ marginBottom: 0 }}>
                            ขณะนี้ไม่มีรายวิชาที่กำลังเรียน ระบบปิดการสแกนลายนิ้วมือ
                        </p>
                    </div>
                )}
            </div>

            {/* Current Semester */}
            <div
                className="card"
                style={{
                    marginBottom: "1rem",
                    padding: "1rem"
                }}
            >
                <h2 style={{ marginTop: 0 }}>
                    ภาคเรียนปัจจุบัน
                </h2>

                {currentSemester ? (
                    <div>
                        <h2 style={{ color: "#16a34a" }}>
                            {currentSemester.semester_name}
                        </h2>

                        <p>
                            <strong>วันเริ่มต้น:</strong>{" "}
                            {formatSemesterDate(
                                currentSemester.start_date
                            )}
                        </p>

                        <p>
                            <strong>วันสิ้นสุด:</strong>{" "}
                            {formatSemesterDate(
                                currentSemester.end_date
                            )}
                        </p>

                        <span className="tag ok">
                            กำลังใช้งาน
                        </span>
                    </div>
                ) : (
                    <p className="hint">
                        ยังไม่มีภาคเรียนที่เปิดใช้งาน
                    </p>
                )}
            </div>

            {/* Current Subject */}
            <div
                className="card"
                style={{
                    marginBottom: "1rem",
                    padding: "1rem"
                }}
            >
                <h2 style={{ marginTop: 0 }}>
                    รายวิชาปัจจุบัน
                </h2>

                <div id="current-subject">
                    {currentSubject?.active ? (
                        <div>
                            <p>
                                <strong>รหัสวิชา:</strong>{" "}
                                {currentSubject.code ?? "-"}
                            </p>

                            <p>
                                <strong>ชื่อวิชา:</strong>{" "}
                                {currentSubject.name ?? "-"}
                            </p>

                            <p>
                                <strong>เวลาเรียน:</strong>{" "}
                                {currentSubject.start_time ?? "-"}
                                {" - "}
                                {currentSubject.end_time ?? "-"}
                            </p>
                        </div>
                    ) : (
                        <p className="hint">
                            ขณะนี้ไม่มีรายวิชาที่กำลังเรียน
                        </p>
                    )}
                </div>
            </div>

            {/* Recent Scan Logs: show only when a subject is active */}
            {currentSubject?.active && (
            <div className="card">
                <div className="table-container">
                    <table
                        className="data-table"
                        id="scan-table"
                    >
                        <thead>
                            <tr>
                                <th>เวลาที่สแกน</th>
                                <th>รหัสนักศึกษา/บุคลากร</th>
                                <th>ชื่อ-นามสกุล</th>
                                <th>หน่วยงาน/สาขา</th>
                                <th>รายวิชา</th>
                                <th>สถานะ</th>
                                <th>จำนวนมาเรียน</th>
                                <th>จำนวนขาดเรียน</th>
                            </tr>
                        </thead>

                        <tbody>
                            {loading ? (
                                <tr>
                                    <td
                                        colSpan="8"
                                        className="empty"
                                    >
                                        กำลังโหลดข้อมูล...
                                    </td>
                                </tr>
                            ) : scans.length === 0 ? (
                                <tr>
                                    <td
                                        colSpan="8"
                                        className="empty"
                                    >
                                        วันนี้ยังไม่มีรายการสแกน
                                    </td>
                                </tr>
                            ) : (
                                scans.map((log, index) => (
                                    <tr
                                        key={
                                            log.id ??
                                            `${log.scanned_at}-${index}`
                                        }
                                    >
                                        <td data-label="เวลาที่สแกน">
                                            {formatScanDate(
                                                log.scanned_at
                                            )}
                                        </td>

                                        <td data-label="รหัสนักศึกษา/บุคลากร">
                                            {log.student_id ?? "-"}
                                        </td>

                                        <td data-label="ชื่อ-นามสกุล">
                                            {log.full_name ?? "-"}
                                        </td>

                                        <td data-label="หน่วยงาน/สาขา">
                                            {log.department ?? "-"}
                                        </td>

                                        <td data-label="รายวิชา">
                                            {log.subject_code ??
                                                log.subject_name ??
                                                "-"}
                                        </td>

                                        <td data-label="สถานะ">
                                            {getStatus(
                                                log.status,
                                                log.fingerprint_id
                                            )}
                                        </td>

                                        <td data-label="จำนวนมาเรียน">
                                            {log.attended_count ?? 0}
                                        </td>

                                        <td data-label="จำนวนขาดเรียน">
                                            {log.absent_count ?? 0}
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>

                {error && (
                    <p
                        className="hint"
                        role="alert"
                    >
                        {error}
                    </p>
                )}
            </div>
            )}

        </>
    );
}

export default CheckIn;
