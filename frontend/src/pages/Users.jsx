import { useCallback, useEffect, useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

function Users() {
  const [formData, setFormData] = useState({
    student_id: "",
    full_name: "",
    department: "",
    section_id: "",
  });

  const [excelFile, setExcelFile] = useState(null);
  const [users, setUsers] = useState([]);
  const [sections, setSections] = useState([]);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);

  const [error, setError] = useState("");
  const [formMessage, setFormMessage] = useState("");
  const [importMessage, setImportMessage] = useState("");
  const [importError, setImportError] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState(null);
  const [deleting, setDeleting] = useState(false);

  // Load Users and Sections
  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const [usersResponse, sectionsResponse] = await Promise.all([
        fetch(`${API_BASE_URL}/api/users`, {
          cache: "no-store",
        }),
        fetch(`${API_BASE_URL}/api/sections`, {
          cache: "no-store",
        }),
      ]);

      if (!usersResponse.ok) {
        throw new Error(`Users API HTTP ${usersResponse.status}`);
      }

      if (!sectionsResponse.ok) {
        throw new Error(`Sections API HTTP ${sectionsResponse.status}`);
      }

      const [usersData, sectionsData] = await Promise.all([
        usersResponse.json(),
        sectionsResponse.json(),
      ]);

      setUsers(Array.isArray(usersData) ? usersData : []);
      setSections(Array.isArray(sectionsData) ? sectionsData : []);
    } catch (err) {
      console.error("Unable to load users:", err);
      setError("ไม่สามารถโหลดข้อมูลผู้ใช้งานได้");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Handle form change
  const handleChange = (event) => {
    const { name, value } = event.target;

    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));

    setFormMessage("");
  };

  // Handle Excel file
  const handleExcelChange = (event) => {
    setExcelFile(event.target.files?.[0] ?? null);
    setImportMessage("");
    setImportError(false);
  };

  // Import Users from Excel
  const handleImport = async (event) => {
    event.preventDefault();

    if (!excelFile) {
      setImportMessage("กรุณาเลือกไฟล์ Excel");
      setImportError(true);
      return;
    }

    try {
      setImporting(true);
      setImportMessage("");
      setImportError(false);

      const formData = new FormData();
      formData.append("excel_file", excelFile);

      const response = await fetch(
        `${API_BASE_URL}/api/users/import`,
        {
          method: "POST",
          body: formData,
        }
      );

      const data = await response.json();

      if (!response.ok) {
        const errorDetails = data.errors
          ?.slice(0, 10)
          .map((item) => `แถว ${item.row}: ${item.message}`)
          .join("\n");

        throw new Error(
          errorDetails
            ? `${data.message}\n${errorDetails}`
            : data.message || "ไม่สามารถ Import ผู้ใช้ได้"
        );
      }

      const result = data.result || {};

      const message =
        `Import เสร็จสิ้น\n` +
        `เพิ่มใหม่ ${result.inserted ?? 0} คน\n` +
        `อัปเดต ${result.updated ?? 0} คน\n` +
        `ข้าม ${result.skipped ?? 0} คน`;

      const errorDetails = result.errors
        ?.slice(0, 10)
        .map((item) => `แถว ${item.row}: ${item.message}`)
        .join("\n");

      setImportMessage(
        errorDetails ? `${message}\n\n${errorDetails}` : message
      );

      setImportError(Boolean(result.errors?.length));

      setExcelFile(null);
      event.target.reset();

      await fetchData();
    } catch (err) {
      console.error("Import users error:", err);
      setImportMessage(
        err.message || "เกิดข้อผิดพลาดในการ Import ผู้ใช้"
      );
      setImportError(true);
    } finally {
      setImporting(false);
    }
  };

  // Create User without fingerprint enrollment
  const handleSubmit = async (event) => {
    event.preventDefault();

    if (
      !formData.student_id.trim() ||
      !formData.full_name.trim()
    ) {
      setFormMessage("กรุณากรอกรหัสนักศึกษาและชื่อ-นามสกุล");
      return;
    }

    if (!formData.section_id) {
      setFormMessage("กรุณาเลือก Section");
      return;
    }

    try {
      setSaving(true);
      setFormMessage("");

      const studentId = formData.student_id.trim();

      const response = await fetch(`${API_BASE_URL}/api/users`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          student_id: studentId,
          full_name: formData.full_name.trim(),
          department: formData.department.trim(),
          section_id: formData.section_id,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.message || "ไม่สามารถบันทึกผู้ใช้ได้"
        );
      }

      setFormMessage("เพิ่มผู้ใช้สำเร็จ");

      setFormData({
        student_id: "",
        full_name: "",
        department: "",
        section_id: "",
      });

      await fetchData();
    } catch (err) {
      console.error("Create user error:", err);
      setFormMessage(
        err.message || "เกิดข้อผิดพลาดในการบันทึก"
      );
    } finally {
      setSaving(false);
    }
  };

  // Enroll fingerprint (not connected yet)
  const handleEnroll = (user) => {
    console.log("Enroll user:", user.id);
  };

  // Delete user
  const handleDelete = (user) => {
    setConfirmDialog({
      user,
      title: "ยืนยันการลบผู้ใช้",
      message: `ต้องการลบผู้ใช้ ${user.full_name} (${user.student_id}) ใช่หรือไม่?`,
      confirmText: "ยืนยันการลบ",
    });
  };

  const handleConfirmDelete = async () => {
    if (!confirmDialog?.user) return;

    const user = confirmDialog.user;

    try {
      setDeleting(true);
      setError("");
      setFormMessage("");

      const response = await fetch(
        `${API_BASE_URL}/api/users/${user.id}`,
        {
          method: "DELETE",
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || "ไม่สามารถลบผู้ใช้ได้");
      }

      setFormMessage(data.message || "ลบผู้ใช้สำเร็จ");
      setConfirmDialog(null);

      await fetchData();
    } catch (err) {
      setError(err.message || "เกิดข้อผิดพลาดในการลบผู้ใช้");
    } finally {
      setDeleting(false);
    }
  };

  // Format date
  const formatDate = (value) => {
    if (!value) return "-";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) return "-";

    return new Intl.DateTimeFormat("th-TH", {
      timeZone: "Asia/Bangkok",
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  };

  return (
    <>
      <div className="page-header">
        <h1>จัดการผู้ใช้งาน</h1>
      </div>

      {/* Import Excel */}
      <div className="card">
        <h2>นำเข้ารายชื่อจาก Excel</h2>

        <p className="hint">
          ไฟล์ Excel ต้องมีหัวคอลัมน์ student_id และ full_name
          สามารถระบุ department และ section หรือ section_id เพิ่มเติมได้
        </p>

        <form
          className="form-grid"
          onSubmit={handleImport}
        >
          <div className="field">
            <label htmlFor="excel_file">
              เลือกไฟล์ Excel
            </label>

            <input
              type="file"
              id="excel_file"
              name="excel_file"
              accept=".xlsx,.xlsm"
              onChange={handleExcelChange}
              disabled={importing}
              required
            />
          </div>

          <div className="field submit">
            <button
              type="submit"
              disabled={!excelFile || importing}
            >
              {importing ? "กำลัง Import..." : "Import Excel"}
            </button>
          </div>

          {importMessage && (
            <div className="field full-width">
              <p
                className={importError ? "flash error" : "flash success"}
                role={importError ? "alert" : "status"}
                style={{ whiteSpace: "pre-line" }}
              >
                {importMessage}
              </p>
            </div>
          )}
        </form>
      </div>

      {/* Add User */}
      <div className="card">
        <h2>เพิ่มผู้ใช้ใหม่ / ลงทะเบียนลายนิ้วมือ</h2>

        <form className="form-grid" onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="student_id">
              รหัสนักศึกษา{" "}
              <span style={{ color: "red" }}>*</span>
            </label>

            <input
              type="text"
              id="student_id"
              name="student_id"
              placeholder="รหัสนักศึกษา"
              value={formData.student_id}
              onChange={handleChange}
              required
            />
          </div>

          <div className="field">
            <label htmlFor="full_name">
              ชื่อ-นามสกุล
            </label>

            <input
              type="text"
              id="full_name"
              name="full_name"
              placeholder="ชื่อ-นามสกุล"
              value={formData.full_name}
              onChange={handleChange}
              required
            />
          </div>

          <div className="field">
            <label htmlFor="department">
              หน่วยงาน/คณะ/สาขา
            </label>

            <input
              type="text"
              id="department"
              name="department"
              placeholder="หน่วยงาน/คณะ/สาขา"
              value={formData.department}
              onChange={handleChange}
            />
          </div>

          <div className="field">
            <label htmlFor="section_id">
              Section
            </label>

            <select
              id="section_id"
              name="section_id"
              value={formData.section_id}
              onChange={handleChange}
              required
            >
              <option value="">
                -- เลือก Section --
              </option>

              {sections.map((section) => (
                <option
                  key={section.id}
                  value={section.id}
                >
                  {section.name}
                </option>
              ))}
            </select>
          </div>

          <div className="field full-width">
            <button
              type="button"
              disabled
              onClick={handleEnroll}
            >
              ลงทะเบียนลายนิ้วมือ
            </button>

            <p className="hint">
              ขณะนี้สามารถบันทึกข้อมูลผู้ใช้ได้โดยไม่ต้องสแกนลายนิ้วมือ
              สามารถลงทะเบียนลายนิ้วมือภายหลังได้
            </p>
          </div>

          <div className="field submit">
            <button type="submit" disabled={saving}>
              {saving ? "กำลังบันทึก..." : "บันทึกผู้ใช้"}
            </button>

            {formMessage && (
              <p className="hint" role="status">
                {formMessage}
              </p>
            )}
          </div>
        </form>
      </div>

      {/* User List */}
      <div className="card">
        <h2>
          รายชื่อผู้ใช้ทั้งหมด ({users.length})
        </h2>

        {error && (
          <p className="hint" role="alert">
            {error}
          </p>
        )}

        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>รหัส</th>
                <th>ชื่อ-นามสกุล</th>
                <th>หน่วยงาน/สาขา</th>
                <th>Section</th>
                <th>สถานะข้อมูล</th>
                <th>ลงทะเบียนเมื่อ</th>
                <th>จัดการ</th>
                <th></th>
              </tr>
            </thead>

            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="8" className="empty">
                    กำลังโหลดข้อมูล...
                  </td>
                </tr>
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan="8" className="empty">
                    ยังไม่มีผู้ใช้ในระบบ
                  </td>
                </tr>
              ) : (
                users.map((user) => (
                  <tr key={user.id}>
                    <td>{user.student_id ?? "-"}</td>
                    <td>{user.full_name ?? "-"}</td>
                    <td>{user.department ?? "-"}</td>
                    <td>{user.section_name ?? "-"}</td>
                    <td>{user.fingerprint_id ? "มีข้อมูล" : "ยังไม่ลงทะเบียน"}</td>
                    <td>{formatDate(user.created_at)}</td>

                    <td>
                      <button
                        type="button"
                        className="btn-enroll"
                        disabled
                        onClick={() => handleEnroll(user)}
                      >
                        ลงทะเบียนลายนิ้วมือ
                      </button>
                    </td>

                    <td>
                      <button
                        type="button"
                        className="btn-delete danger"
                        onClick={() => handleDelete(user)}
                      >
                        ลบ
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
              if (!deleting) setConfirmDialog(null);
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
                  disabled={deleting}
                >
                  ยกเลิก
                </button>

                <button
                  type="button"
                  className="btn-danger"
                  onClick={handleConfirmDelete}
                  disabled={deleting}
                >
                  {deleting ? "กำลังลบ..." : confirmDialog.confirmText}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

export default Users;
