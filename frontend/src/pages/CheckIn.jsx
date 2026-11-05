import { useEffect, useState } from "react";

import {
    formatScanDate,
    getThaiDateString,
    getTodayThaiDateString,
} from "../services/legacy";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";


function CheckIn() {
    const [currentSubject, setCurrentSubject] = useState(null);
    const [currentSemester, setCurrentSemester] = useState(null);

    const [scans, setScans] = useState([]);

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

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

            {/* Recent Scan Logs */}
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
                                        <td>
                                            {formatScanDate(
                                                log.scanned_at
                                            )}
                                        </td>

                                        <td>
                                            {log.student_id ?? "-"}
                                        </td>

                                        <td>
                                            {log.full_name ?? "-"}
                                        </td>

                                        <td>
                                            {log.department ?? "-"}
                                        </td>

                                        <td>
                                            {log.subject_code ??
                                                log.subject_name ??
                                                "-"}
                                        </td>

                                        <td>
                                            {getStatus(
                                                log.status,
                                                log.fingerprint_id
                                            )}
                                        </td>

                                        <td>
                                            {log.attended_count ?? 0}
                                        </td>

                                        <td>
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
        </>
    );
}

export default CheckIn;
