
import { useCallback, useEffect, useState } from "react";

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || ""
).replace(/\/+$/, "");

function Sections() {
  const [sectionName, setSectionName] = useState("");
  const [sections, setSections] = useState([]);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState(null);

  const [error, setError] = useState("");
  const [formMessage, setFormMessage] = useState("");
  const [confirmDialog, setConfirmDialog] = useState(null);
  const [resultDialog, setResultDialog] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);

  // Load Sections
  const fetchSections = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const response = await fetch(`${API_BASE_URL}/api/sections`, {
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error(`Sections API HTTP ${response.status}`);
      }

      const data = await response.json();
      setSections(data);
    } catch (err) {
      console.error("Unable to load sections:", err);
      setError("ไม่สามารถโหลดข้อมูล Section ได้");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSections();
  }, [fetchSections]);

  // Add Section
  const handleSubmit = async (event) => {
    event.preventDefault();

    const name = sectionName.trim();

    if (!name) {
      setResultDialog({
        type: "error",
        title: "กรุณากรอกข้อมูล",
        message: "กรุณากรอกชื่อ Section ก่อนเพิ่มข้อมูล",
      });
      return;
    }

    try {
      setSaving(true);
      setFormMessage("");

      const response = await fetch(`${API_BASE_URL}/api/sections`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ name }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || "ไม่สามารถเพิ่ม Section ได้");
      }

      setSectionName("");
      await fetchSections();

      setResultDialog({
        type: "success",
        title: "เพิ่ม Section สำเร็จ!",
        message: `เพิ่ม Section "${name}" เรียบร้อยแล้ว`,
      });
    } catch (err) {
      console.error("Create section error:", err);
      setResultDialog({
        type: "error",
        title: "เพิ่ม Section ไม่สำเร็จ",
        message: err.message || "เกิดข้อผิดพลาดในการเพิ่ม Section",
      });
    } finally {
      setSaving(false);
    }
  };

  // Delete Section
  // Delete Section - Open Popup
  const handleDelete = (section) => {
    setConfirmDialog({
      section,
      title: "ยืนยันการลบ Section",
      message: `ต้องการลบ Section "${section.name}" ใช่หรือไม่?`,
      confirmText: "ยืนยันการลบ",
    });
  };

  // Confirm Delete Section
  const handleConfirmDelete = async () => {
    if (!confirmDialog?.section) return;

    const section = confirmDialog.section;

    try {
      setActionLoading(true);
      setDeletingId(section.id);
      setError("");
      setFormMessage("");

      const response = await fetch(
        `${API_BASE_URL}/api/sections/${section.id}`,
        {
          method: "DELETE",
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || "ไม่สามารถลบ Section ได้");
      }

      setConfirmDialog(null);
      await fetchSections();

      setResultDialog({
        type: "success",
        title: "ลบ Section สำเร็จ!",
        message: `ลบ Section "${section.name}" เรียบร้อยแล้ว`,
      });
    } catch (err) {
      console.error("Delete section error:", err);
      setConfirmDialog(null);
      setResultDialog({
        type: "error",
        title: "ลบ Section ไม่สำเร็จ",
        message: err.message || "เกิดข้อผิดพลาดในการลบ Section",
      });
    } finally {
      setActionLoading(false);
      setDeletingId(null);
    }
  };

  return (
    <>
      <div className="page-header">
        <h1>กลุ่มเรียน</h1>
        <p className="hint">
          จัดการกลุ่มเรียนที่ใช้ในระบบ
        </p>
      </div>

      {/* Add Section */}
      <div className="card">
        <h2>เพิ่ม Section</h2>

        <form className="form-grid" onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="section_name">ชื่อ Section</label>

            <input
              type="text"
              id="section_name"
              name="name"
              maxLength={100}
              placeholder="ชื่อ Section"
              value={sectionName}
              onChange={(event) => {
                setSectionName(event.target.value);
                setFormMessage("");
              }}
              required
            />
          </div>

          <div className="field submit">
            <button type="submit" disabled={saving}>
              {saving ? "กำลังบันทึก..." : "เพิ่ม Section"}
            </button>

          </div>
        </form>
      </div>

      {/* Section List */}
      <div className="card">
        <h2>รายการ Section ({sections.length})</h2>

        {error && (
          <p className="hint" role="alert">
            {error}
          </p>
        )}

        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>ชื่อ Section</th>
                <th>จัดการ</th>
              </tr>
            </thead>

            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="3" className="empty">
                    กำลังโหลดข้อมูล...
                  </td>
                </tr>
              ) : sections.length === 0 ? (
                <tr>
                  <td colSpan="3" className="empty">
                    ยังไม่มีข้อมูล Section
                  </td>
                </tr>
              ) : (
                sections.map((section) => (
                  <tr key={section.id}>
                    <td data-label="ID">{section.id}</td>
                    <td data-label="ชื่อ Section">{section.name}</td>
                    <td data-label="จัดการ">
                      <button
                        type="button"
                        className="btn-delete"
                        disabled={deletingId === section.id}
                        onClick={() => handleDelete(section)}
                      >
                        {deletingId === section.id ? "กำลังลบ..." : "ลบ"}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
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
              <div className="confirm-modal-icon">!</div>

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
                  className="btn-danger"
                  onClick={handleConfirmDelete}
                  disabled={actionLoading}
                >
                  {actionLoading
                    ? "กำลังลบ..."
                    : confirmDialog.confirmText}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {resultDialog && (
        <div
          className="confirm-modal-overlay"
          onClick={() => setResultDialog(null)}
        >
          <div
            className="confirm-modal success-modal"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="success-modal-icon">
              {resultDialog.type === "success" ? "✓" : "!"}
            </div>
            <h2>{resultDialog.title}</h2>
            <p>{resultDialog.message}</p>
            <div className="confirm-modal-actions">
              <button
                type="button"
                onClick={() => setResultDialog(null)}
              >
                ตกลง
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default Sections;
