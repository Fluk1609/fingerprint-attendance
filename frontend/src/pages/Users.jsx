import { useCallback, useEffect, useState } from "react";
import { scannerRequest, restartEnrollment } from "../services/scanner-agent.service";

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || ""
).replace(/\/+$/, "");

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
  const [enrollingUserId, setEnrollingUserId] = useState(null);
  const [enrollMessage, setEnrollMessage] = useState("");
  const [enrollScanCount, setEnrollScanCount] = useState(0);
  const [successDialog, setSuccessDialog] = useState(null);
  const [restartEnrollDialog, setRestartEnrollDialog] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const ITEMS_PER_PAGE = 10;

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
        `Import เสร็จสิ้น ` +
        `เพิ่มใหม่ ${result.inserted ?? 0} คน ` +
        `อัปเดต ${result.updated ?? 0} คน ` +
        `ข้าม ${result.skipped ?? 0} คน `;

      const errorDetails = result.errors
        ?.slice(0, 10)
        .map((item) => `แถว ${item.row}: ${item.message}`)
        .join("\n");

      setImportMessage("");
      setImportError(false);

      setExcelFile(null);
      event.target.reset();

      await fetchData();

      setSuccessDialog({
        title: result.errors?.length ? "Import เสร็จสิ้น (มีบางรายการผิดพลาด)" : "Import สำเร็จ!",
        message: errorDetails ? `${message}\n\n${errorDetails}` : message,
      });
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

      setFormMessage("");

      setFormData({
        student_id: "",
        full_name: "",
        department: "",
        section_id: "",
      });

      await fetchData();

      setSuccessDialog({
        title: "บันทึกผู้ใช้สำเร็จ!",
        message: `เพิ่มข้อมูล ${studentId} เรียบร้อยแล้ว`,
      });
    } catch (err) {
      console.error("Create user error:", err);
      setFormMessage(
        err.message || "เกิดข้อผิดพลาดในการบันทึก"
      );
    } finally {
      setSaving(false);
    }
  };

  // Enroll fingerprint through the local Scanner Agent.
  // If another enrollment is active, ask before clearing it and starting over.
  const handleEnroll = async (user, restart = false) => {
    if (enrollingUserId !== null) return;

    try {
      setEnrollingUserId(user.id);
      setEnrollScanCount(0);
      setEnrollMessage(`กำลังเริ่มลงทะเบียน ${user.full_name}...`);

      const startData = restart
        ? await restartEnrollment(user.id)
        : await scannerRequest(
            "/api/scanner/enroll/start",
            {
              method: "POST",
              body: JSON.stringify({ user_id: user.id }),
            }
          );

      for (let scan = 1; scan <= 3; scan += 1) {
        setEnrollScanCount(scan);
        setEnrollMessage(
          `กรุณาวางนิ้วของ ${user.full_name} บนเครื่องสแกน (ครั้งที่ ${scan}/3)`
        );

        const captureData = await scannerRequest(
          "/api/scanner/enroll/capture",
          { method: "POST" }
        );

        setEnrollMessage(`สแกนสำเร็จ ${captureData.scan_count}/3 ครั้ง`);
      }

      setEnrollMessage("กำลังรวม Template และบันทึกลงฐานข้อมูล...");

      const finishData = await scannerRequest(
        "/api/scanner/enroll/finish",
        { method: "POST" }
      );

      setEnrollMessage("");
      setFormMessage("");

      await fetchData();

      setSuccessDialog({
        title: "ลงทะเบียนสำเร็จ!",
        message: `ลงทะเบียนลายนิ้วมือของ ${user.full_name} เรียบร้อยแล้ว`,
      });
    } catch (err) {
      console.error("Fingerprint enrollment error:", err);

      if (err.status === 409 && !restart) {
        // Keep the existing enrollment untouched until the user confirms.
        setEnrollMessage("");
        setRestartEnrollDialog(user);
        return;
      }

      setEnrollMessage(
        err.status === 401
          ? "กรุณา Pair เครื่องสแกนก่อนลงทะเบียน"
          : err.message || "เกิดข้อผิดพลาดในการลงทะเบียน"
      );

      // A 409 means another enrollment is active. Do not cancel it here:
      // the user must explicitly confirm before it is replaced.
      if (err.status !== 409) {
        try {
          await scannerRequest("/api/scanner/enroll/cancel", {
            method: "POST",
          });
        } catch {
          // Scanner Agent may be offline.
        }
      }
    } finally {
      setEnrollingUserId(null);
      setEnrollScanCount(0);
    }
  };

  const handleConfirmRestartEnrollment = async () => {
    const user = restartEnrollDialog;
    if (!user) return;

    setRestartEnrollDialog(null);
    await handleEnroll(user, true);
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

      setConfirmDialog(null);
      await fetchData();
      setSuccessDialog({
        title: "ลบผู้ใช้สำเร็จ!",
        message: data.message || `ลบข้อมูล ${user.full_name} (${user.student_id}) เรียบร้อยแล้ว`,
      });
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

  const filteredUsers = users.filter((user) => {
    const keyword = searchTerm.trim().toLowerCase();
    if (!keyword) return true;

    return [
      user.student_id,
      user.full_name,
      user.department,
      user.section_name,
      user.fingerprint_id ? "มีข้อมูล" : "ยังไม่ลงทะเบียน",
    ].some((value) => String(value ?? "").toLowerCase().includes(keyword));
  });

  const totalPages = Math.max(1, Math.ceil(filteredUsers.length / ITEMS_PER_PAGE));
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const paginatedUsers = filteredUsers.slice(
    (safeCurrentPage - 1) * ITEMS_PER_PAGE,
    safeCurrentPage * ITEMS_PER_PAGE
  );

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

          {/* <div className="field full-width">
            <button type="button" disabled>
              ลงทะเบียนลายนิ้วมือหลังบันทึกผู้ใช้
            </button>

            <p className="hint">
              ขณะนี้สามารถบันทึกข้อมูลผู้ใช้ได้โดยไม่ต้องสแกนลายนิ้วมือ
              สามารถลงทะเบียนลายนิ้วมือภายหลังได้
            </p>
          </div> */}

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
          รายชื่อผู้ใช้ทั้งหมด ({filteredUsers.length})
        </h2>
        <div
          className="table-toolbar"
          style={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "12px",
            margin: "12px 0",
          }}
        >
          <input
            type="search"
            value={searchTerm}
            onChange={(event) => {
              setSearchTerm(event.target.value);
              setCurrentPage(1);
            }}
            placeholder="ค้นหารหัส ชื่อ หน่วยงาน หรือ Section..."
            aria-label="ค้นหาผู้ใช้"
            style={{
              flex: "1 1 280px",
              maxWidth: "420px",
              padding: "10px 12px",
              border: "1px solid #d1d5db",
              borderRadius: "8px",
            }}
          />
          <span className="hint">
            แสดง {paginatedUsers.length} จาก {filteredUsers.length} รายการ
          </span>
        </div>
        {enrollMessage && (
          <p className="hint" role="status" style={{ whiteSpace: "pre-line" }}>
            {enrollMessage}
          </p>
        )}

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
              ) : filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan="8" className="empty">
                    ยังไม่มีผู้ใช้ในระบบ
                  </td>
                </tr>
              ) : (
                paginatedUsers.map((user) => (
                  <tr key={user.id}>
                    <td data-label="รหัส">{user.student_id ?? "-"}</td>
                    <td data-label="ชื่อ-นามสกุล">{user.full_name ?? "-"}</td>
                    <td data-label="หน่วยงาน/สาขา">{user.department ?? "-"}</td>
                    <td data-label="Section">{user.section_name ?? "-"}</td>
                    <td data-label="สถานะข้อมูล">{user.fingerprint_id ? "มีข้อมูล" : "ยังไม่ลงทะเบียน"}</td>
                    <td data-label="ลงทะเบียนเมื่อ">{formatDate(user.created_at)}</td>

                    <td data-label="จัดการ">
                      <button
                        type="button"
                        className="btn-enroll"
                        disabled={enrollingUserId !== null}
                        onClick={() => handleEnroll(user)}
                      >
                        {enrollingUserId === user.id
                          ? enrollScanCount > 0
                            ? `กำลังสแกน ${enrollScanCount}/3`
                            : "กำลังเตรียม..."
                          : "ลงทะเบียนลายนิ้วมือ"}
                      </button>
                    </td>

                    <td data-label="ลบ">
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
        {filteredUsers.length > 0 && (
          <div
            className="table-pagination"
            style={{
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "12px",
              marginTop: "16px",
            }}
          >
            <span className="hint">
              หน้า {safeCurrentPage} / {totalPages}
            </span>
            <div style={{ display: "flex", gap: "8px" }}>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
                disabled={safeCurrentPage === 1}
              >
                ก่อนหน้า
              </button>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}
                disabled={safeCurrentPage === totalPages}
              >
                ถัดไป
              </button>
            </div>
          </div>
        )}
        {restartEnrollDialog && (
          <div
            className="confirm-modal-overlay"
            onClick={() => setRestartEnrollDialog(null)}
          >
            <div
              className="confirm-modal"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="confirm-modal-icon">!</div>

              <h2>มีรายการลงทะเบียนลายนิ้วมือค้างอยู่</h2>

              <p>
                พบรายการลงทะเบียนก่อนหน้าที่ยังไม่เสร็จสมบูรณ์
                ต้องการยกเลิกรายการเดิมและเริ่มลงทะเบียนลายนิ้วมือของ{" "}
                <strong>{restartEnrollDialog.full_name}</strong> ใหม่หรือไม่?
              </p>

              <div className="confirm-modal-actions">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setRestartEnrollDialog(null)}
                >
                  ยกเลิก
                </button>

                <button
                  type="button"
                  onClick={handleConfirmRestartEnrollment}
                >
                  ลงทะเบียนใหม่
                </button>
              </div>
            </div>
          </div>
        )}

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
        {successDialog && (
          <div className="confirm-modal-overlay">
            <div className="confirm-modal success-modal">
              <div className="success-modal-icon">
                ✓
              </div>

              <h2>{successDialog.title}</h2>

              <p style={{ whiteSpace: "pre-line" }}>{successDialog.message}</p>

              <div className="confirm-modal-actions">
                <button
                  type="button"
                  onClick={() => setSuccessDialog(null)}
                >
                  ตกลง
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
