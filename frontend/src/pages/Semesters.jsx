import { useCallback, useEffect, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

const initialForm = {
    semester_name: "",
    start_date: "",
    end_date: "",
};

function Semesters() {
    const [semesters, setSemesters] = useState([]);
    const [formData, setFormData] = useState(initialForm);
    const [editingId, setEditingId] = useState(null);

    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");
    const [message, setMessage] = useState("");
    const [confirmDialog, setConfirmDialog] = useState(null);
    const [actionLoading, setActionLoading] = useState(false);

    const activeSemester = semesters.find(
        (semester) => semester.is_active
    );

    const fetchSemesters = useCallback(async () => {
        try {
            setLoading(true);

            const response = await fetch(
                `${API_BASE_URL}/api/semesters`,
                { cache: "no-store" }
            );

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || "ไม่สามารถโหลดข้อมูลได้");
            }

            setSemesters(Array.isArray(data) ? data : []);
            setError("");
        } catch (err) {
            console.error(err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchSemesters();
    }, [fetchSemesters]);

    const handleChange = (event) => {
        const { name, value } = event.target;

        setFormData((prev) => ({
            ...prev,
            [name]: value,
        }));
    };

    const resetForm = () => {
        setFormData(initialForm);
        setEditingId(null);
    };

    const handleSubmit = async (event) => {
        event.preventDefault();

        if (!formData.semester_name.trim()) {
            setError("กรุณาระบุชื่อภาคเรียน");
            return;
        }

        if (!formData.start_date || !formData.end_date) {
            setError("กรุณาระบุวันที่เริ่มต้นและสิ้นสุด");
            return;
        }

        if (formData.start_date > formData.end_date) {
            setError("วันสิ้นสุดต้องไม่น้อยกว่าวันเริ่มต้น");
            return;
        }

        try {
            setSaving(true);
            setError("");
            setMessage("");

            const url = editingId
                ? `${API_BASE_URL}/api/semesters/${editingId}`
                : `${API_BASE_URL}/api/semesters`;

            const response = await fetch(url, {
                method: editingId ? "PUT" : "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(formData),
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || "บันทึกข้อมูลไม่สำเร็จ");
            }

            setMessage(data.message);
            resetForm();
            await fetchSemesters();
        } catch (err) {
            setError(err.message);
        } finally {
            setSaving(false);
        }
    };

    const handleEdit = (semester) => {
        if (semester.is_active) {
            setError("กรุณาปิดภาคเรียนก่อนแก้ไขข้อมูล");
            return;
        }

        setFormData({
            semester_name: semester.semester_name,
            start_date: semester.start_date,
            end_date: semester.end_date,
        });

        setEditingId(semester.id);
        setError("");
        setMessage("");

        window.scrollTo({
            top: 0,
            behavior: "smooth",
        });
    };

    const handleActivate = (semester) => {
        setConfirmDialog({
            type: "activate",
            semester,
            title: "ยืนยันการเปิดภาคเรียน",
            message: `ต้องการเปิดภาคเรียน ${semester.semester_name} ใช่หรือไม่? ภาคเรียนที่เปิดอยู่ในปัจจุบันจะถูกปิด`,
            confirmText: "เปิดภาคเรียน",
        });
    };

    const handleClose = (semester) => {
        setConfirmDialog({
            type: "close",
            semester,
            title: "ยืนยันการปิดภาคเรียน",
            message: `ต้องการปิดภาคเรียน ${semester.semester_name} ใช่หรือไม่?`,
            confirmText: "ปิดภาคเรียน",
        });
    };

    const handleDelete = (semester) => {
        setConfirmDialog({
            type: "delete",
            semester,
            title: "ยืนยันการลบภาคเรียน",
            message: `ต้องการลบภาคเรียน ${semester.semester_name} ใช่หรือไม่? การดำเนินการนี้ไม่สามารถย้อนกลับได้`,
            confirmText: "ยืนยันการลบ",
        });
    };

    const handleConfirmAction = async () => {
        if (!confirmDialog) return;

        const { type, semester } = confirmDialog;

        const endpoints = {
            activate: {
                url: `/api/semesters/${semester.id}/activate`,
                method: "PUT",
                error: "เปิดภาคเรียนไม่สำเร็จ",
            },
            close: {
                url: `/api/semesters/${semester.id}/close`,
                method: "PUT",
                error: "ปิดภาคเรียนไม่สำเร็จ",
            },
            delete: {
                url: `/api/semesters/${semester.id}`,
                method: "DELETE",
                error: "ลบภาคเรียนไม่สำเร็จ",
            },
        };

        const action = endpoints[type];
        if (!action) return;

        try {
            setActionLoading(true);
            setError("");
            setMessage("");

            const response = await fetch(
                `${API_BASE_URL}${action.url}`,
                { method: action.method }
            );

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || action.error);
            }

            setMessage(data.message);
            setConfirmDialog(null);

            await fetchSemesters();
        } catch (err) {
            setError(err.message);
        } finally {
            setActionLoading(false);
        }
    };

    const formatDate = (value) => {
        if (!value) return "-";

        return new Date(`${value}T00:00:00`).toLocaleDateString(
            "th-TH",
            {
                day: "2-digit",
                month: "short",
                year: "numeric",
            }
        );
    };

    return (
        <div className="semester-page">
            <div className="page-header">
                <h1>จัดการภาคเรียน</h1>
            </div>

            {/* Active Semester */}
            <div className="card" style={{ marginBottom: "1rem", padding: "1rem" }}>
                <h2 style={{ marginTop: 0 }}>ภาคเรียนปัจจุบัน</h2>

                {activeSemester ? (
                    <div>
                        <h2 style={{ color: "#16a34a" }}>
                            {activeSemester.semester_name}
                        </h2>

                        <p>
                            <strong>วันเริ่มต้น:</strong>{" "}
                            {formatDate(activeSemester.start_date)}
                        </p>

                        <p>
                            <strong>วันสิ้นสุด:</strong>{" "}
                            {formatDate(activeSemester.end_date)}
                        </p>

                        <span className="tag ok">กำลังใช้งาน</span>
                    </div>
                ) : (
                    <p className="hint">
                        ยังไม่มีภาคเรียนที่เปิดใช้งาน
                    </p>
                )}
            </div>

            {/* Messages */}
            {error && (
                <div className="hint" role="alert" style={{ marginBottom: "1rem" }}>
                    {error}
                </div>
            )}

            {message && (
                <div style={{ color: "#16a34a", marginBottom: "1rem" }}>
                    {message}
                </div>
            )}

            {/* Create / Edit Form */}
            <div className="card" style={{ marginBottom: "1rem", padding: "1rem" }}>
                <h2 style={{ marginTop: 0 }}>
                    {editingId ? "แก้ไขภาคเรียน" : "เพิ่มภาคเรียน"}
                </h2>

                <form onSubmit={handleSubmit} className="semester-form">
                    <div className="semester-form-grid">
                        <div className="form-group">
                            <label htmlFor="semester_name">ชื่อภาคเรียน</label>
                            <input
                                id="semester_name"
                                type="text"
                                name="semester_name"
                                value={formData.semester_name}
                                onChange={handleChange}
                                placeholder="เช่น 2/2569"
                                required
                            />
                        </div>

                        <div className="form-group">
                            <label htmlFor="start_date">วันเริ่มภาคเรียน</label>
                            <input
                                id="start_date"
                                type="date"
                                name="start_date"
                                value={formData.start_date}
                                onChange={handleChange}
                                required
                            />
                        </div>

                        <div className="form-group">
                            <label htmlFor="end_date">วันสิ้นสุดภาคเรียน</label>
                            <input
                                id="end_date"
                                type="date"
                                name="end_date"
                                value={formData.end_date}
                                onChange={handleChange}
                                min={formData.start_date || undefined}
                                required
                            />
                        </div>
                    </div>

                    <div className="semester-form-actions">
                        <button type="submit" disabled={saving}>
                            {saving
                                ? "กำลังบันทึก..."
                                : editingId
                                    ? "บันทึกการแก้ไข"
                                    : "เพิ่มภาคเรียน"}
                        </button>

                        {editingId && (
                            <button
                                type="button"
                                className="btn-secondary"
                                onClick={resetForm}
                            >
                                ยกเลิก
                            </button>
                        )}
                    </div>
                </form>
            </div>

            {/* Semester History */}
            <div className="card">
                <h2 style={{ marginTop: 0 }}>ประวัติภาคเรียน</h2>

                <div className="table-container">
                    <table className="data-table">
                        <thead>
                            <tr>
                                <th>ภาคเรียน</th>
                                <th>วันเริ่มต้น</th>
                                <th>วันสิ้นสุด</th>
                                <th>สถานะ</th>
                                <th>จัดการ</th>
                            </tr>
                        </thead>

                        <tbody>
                            {loading ? (
                                <tr>
                                    <td colSpan="5" className="empty">
                                        กำลังโหลดข้อมูล...
                                    </td>
                                </tr>
                            ) : semesters.length === 0 ? (
                                <tr>
                                    <td colSpan="5" className="empty">
                                        ยังไม่มีข้อมูลภาคเรียน
                                    </td>
                                </tr>
                            ) : (
                                semesters.map((semester) => (
                                    <tr key={semester.id}>
                                        <td>{semester.semester_name}</td>

                                        <td>{formatDate(semester.start_date)}</td>

                                        <td>{formatDate(semester.end_date)}</td>

                                        <td>
                                            {semester.is_active ? (
                                                <span className="tag ok">
                                                    กำลังใช้งาน
                                                </span>
                                            ) : (
                                                <span className="tag">
                                                    ปิดใช้งาน
                                                </span>
                                            )}
                                        </td>

                                        <td>
                                            <div
                                                style={{
                                                    display: "flex",
                                                    flexWrap: "wrap",
                                                    gap: "0.4rem",
                                                }}
                                            >
                                                {semester.is_active ? (
                                                    <button
                                                        type="button"
                                                        className="btn-secondary"
                                                        onClick={() => handleClose(semester)}
                                                    >
                                                        ปิดภาคเรียน
                                                    </button>
                                                ) : (
                                                    <>
                                                        <button
                                                            type="button"
                                                            onClick={() => handleActivate(semester)}
                                                        >
                                                            เปิดภาคเรียน
                                                        </button>

                                                        <button
                                                            type="button"
                                                            className="btn-secondary"
                                                            onClick={() => handleEdit(semester)}
                                                        >
                                                            แก้ไข
                                                        </button>

                                                        <button
                                                            type="button"
                                                            className="btn-danger"
                                                            onClick={() => handleDelete(semester)}
                                                        >
                                                            ลบ
                                                        </button>
                                                    </>
                                                )}
                                            </div>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
            {confirmDialog && (
                <div
                    className="confirm-modal-overlay"
                    onClick={() => {
                        if (!actionLoading) setConfirmDialog(null);
                    }}
                >
                    <div
                        className="confirm-modal"
                        onClick={(event) => event.stopPropagation()}
                    >
                        <div className="confirm-modal-icon">
                            {confirmDialog.type === "delete" ? "!" : "?"}
                        </div>

                        <h2>{confirmDialog.title}</h2>

                        <p>{confirmDialog.message}</p>

                        <div className="confirm-modal-actions">
                            <button
                                type="button"
                                className="btn-secondary"
                                onClick={() => setConfirmDialog(null)}
                                disabled={actionLoading}
                            >
                                ยกเลิก
                            </button>

                            <button
                                type="button"
                                className={
                                    confirmDialog.type === "delete"
                                        ? "btn-danger"
                                        : "btn-confirm"
                                }
                                onClick={handleConfirmAction}
                                disabled={actionLoading}
                            >
                                {actionLoading
                                    ? "กำลังดำเนินการ..."
                                    : confirmDialog.confirmText}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

export default Semesters;
