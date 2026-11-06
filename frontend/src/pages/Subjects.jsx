import { useCallback, useEffect, useState } from "react";

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || ""
).replace(/\/+$/, "");

const DAYS = [
  ["Monday", "วันจันทร์"],
  ["Tuesday", "วันอังคาร"],
  ["Wednesday", "วันพุธ"],
  ["Thursday", "วันพฤหัสบดี"],
  ["Friday", "วันศุกร์"],
  ["Saturday", "วันเสาร์"],
  ["Sunday", "วันอาทิตย์"],
];

function formatTime(value) {
  const digits = value.replace(/\D/g, "").slice(0, 4);

  if (digits.length > 2) {
    return `${digits.slice(0, 2)}:${digits.slice(2)}`;
  }

  return digits;
}

function formatDays(days) {
  if (!Array.isArray(days) || days.length === 0) return "-";

  return days
    .map((day) => DAYS.find(([value]) => value === day)?.[1] || day)
    .join(", ");
}

function Subjects() {
  const [formData, setFormData] = useState({
    code: "",
    name: "",
    section_id: "",
    class_days: [],
    start_time: "",
    end_time: "",
    late_after_minutes: "0",
  });

  const [sections, setSections] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [excelFile, setExcelFile] = useState(null);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [importing, setImporting] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [editingId, setEditingId] = useState(null);

  const [error, setError] = useState("");
  const [formMessage, setFormMessage] = useState("");
  const [importMessage, setImportMessage] = useState("");
  const [importError, setImportError] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [resultDialog, setResultDialog] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const ITEMS_PER_PAGE = 10;

  const showResult = (type, title, message) => {
    setResultDialog({ type, title, message });
  };

  // Load Subjects and Sections
  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const [subjectsResponse, sectionsResponse] = await Promise.all([
        fetch(`${API_BASE_URL}/api/subjects`, {
          cache: "no-store",
        }),
        fetch(`${API_BASE_URL}/api/sections`, {
          cache: "no-store",
        }),
      ]);

      if (!subjectsResponse.ok) {
        throw new Error(`Subjects API HTTP ${subjectsResponse.status}`);
      }

      if (!sectionsResponse.ok) {
        throw new Error(`Sections API HTTP ${sectionsResponse.status}`);
      }

      const [subjectsData, sectionsData] = await Promise.all([
        subjectsResponse.json(),
        sectionsResponse.json(),
      ]);

      setSubjects(Array.isArray(subjectsData) ? subjectsData : []);
      setSections(Array.isArray(sectionsData) ? sectionsData : []);
    } catch (err) {
      console.error("Unable to load subjects:", err);
      setError("ไม่สามารถโหลดข้อมูลรายวิชาได้");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleEdit = (subject) => {
    setEditingId(subject.id);

    setFormData({
      code: subject.code || "",
      name: subject.name || "",
      section_id: String(subject.section_id || ""),
      class_days: subject.class_days || [],
      start_time: String(subject.start_time || "").slice(0, 5),
      end_time: String(subject.end_time || "").slice(0, 5),
      late_after_minutes: String(subject.late_after_minutes ?? 0),
    });

    setFormMessage("");
    setError("");

    // เลื่อนกลับไปยังฟอร์ม
    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };

  const handleCancelEdit = () => {
    setEditingId(null);

    setFormData({
      code: "",
      name: "",
      section_id: "",
      class_days: [],
      start_time: "",
      end_time: "",
      late_after_minutes: "0",
    });

    setFormMessage("");
  };

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Handle Form Change
  const handleChange = (event) => {
    const { name, value } = event.target;

    setFormData((prev) => ({
      ...prev,
      [name]: value,
    }));

    setFormMessage("");
  };

  // Handle Days Change
  const handleDaysChange = (event) => {
    const { value, checked } = event.target;

    setFormData((prev) => ({
      ...prev,
      class_days: checked
        ? [...prev.class_days, value]
        : prev.class_days.filter((day) => day !== value),
    }));

    setFormMessage("");
  };

  // Handle Time Change
  const handleTimeChange = (event) => {
    const { name, value } = event.target;

    setFormData((prev) => ({
      ...prev,
      [name]: formatTime(value),
    }));

    setFormMessage("");
  };

  // Handle Excel Change
  const handleExcelChange = (event) => {
    setExcelFile(event.target.files?.[0] ?? null);
    setImportMessage("");
    setImportError(false);
  };

  // Import Subjects from Excel
  const handleImport = async (event) => {
    event.preventDefault();

    if (!excelFile) {
      showResult("error", "ไม่สามารถ Import ได้", "กรุณาเลือกไฟล์ Excel");
      return;
    }

    try {
      setImporting(true);
      setImportMessage("");
      setImportError(false);

      const formData = new FormData();
      formData.append("subject_file", excelFile);

      const response = await fetch(
        `${API_BASE_URL}/api/subjects/import`,
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
            : data.message || "ไม่สามารถ Import รายวิชาได้"
        );
      }

      const inserted = data.result?.inserted ?? 0;

      setImportMessage("");

      setExcelFile(null);
      event.target.reset();

      await fetchData();
      showResult(
        "success",
        "Import รายวิชาสำเร็จ!",
        `นำเข้ารายวิชาทั้งหมด ${inserted} รายการเรียบร้อยแล้ว`
      );
    } catch (err) {
      console.error("Import subjects error:", err);
      setImportMessage("");
      showResult(
        "error",
        "Import รายวิชาไม่สำเร็จ",
        err.message || "เกิดข้อผิดพลาดในการ Import รายวิชา"
      );
    } finally {
      setImporting(false);
    }
  };

  // Create Subject
  const handleSubmit = async (event) => {
    event.preventDefault();

    if (!sections.length) {
      showResult("error", "ไม่สามารถบันทึกได้", "กรุณาเพิ่ม Section ก่อนเพิ่มรายวิชา");
      return;
    }

    if (!formData.class_days.length) {
      showResult("error", "ข้อมูลไม่ครบถ้วน", "กรุณาเลือกวันเรียนอย่างน้อย 1 วัน");
      return;
    }

    const timePattern = /^([01]\d|2[0-3]):[0-5]\d$/;

    if (
      !timePattern.test(formData.start_time) ||
      !timePattern.test(formData.end_time)
    ) {
      showResult("error", "รูปแบบเวลาไม่ถูกต้อง", "กรุณากรอกเวลาให้ถูกต้อง เช่น 08:00");
      return;
    }

    if (formData.start_time >= formData.end_time) {
      showResult("error", "ช่วงเวลาไม่ถูกต้อง", "เวลาเลิกเรียนต้องมากกว่าเวลาเริ่มเรียน");
      return;
    }

    const lateMinutes = Number(formData.late_after_minutes);

    if (
      !Number.isInteger(lateMinutes) ||
      lateMinutes < 0
    ) {
      showResult("error", "ข้อมูลไม่ถูกต้อง", "นาทีผ่อนผันต้องเป็นตัวเลข 0 ขึ้นไป");
      return;
    }

    try {
      setSaving(true);
      setFormMessage("");

      const response = await fetch(
        editingId
          ? `${API_BASE_URL}/api/subjects/${editingId}`
          : `${API_BASE_URL}/api/subjects`,
        {
          method: editingId ? "PUT" : "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            code: formData.code.trim(),
            name: formData.name.trim(),
            section_id: formData.section_id,
            class_days: formData.class_days,
            start_time: formData.start_time,
            end_time: formData.end_time,
            late_after_minutes: lateMinutes,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || "ไม่สามารถเพิ่มรายวิชาได้");
      }

      const wasEditing = Boolean(editingId);
      setFormMessage("");

      setEditingId(null);

      setFormData({
        code: "",
        name: "",
        section_id: "",
        class_days: [],
        start_time: "",
        end_time: "",
        late_after_minutes: "0",
      });

      await fetchData();
      showResult(
        "success",
        wasEditing ? "แก้ไขรายวิชาสำเร็จ!" : "เพิ่มรายวิชาสำเร็จ!",
        wasEditing ? "บันทึกการแก้ไขรายวิชาเรียบร้อยแล้ว" : "เพิ่มรายวิชาใหม่เรียบร้อยแล้ว"
      );
    } catch (err) {
      console.error("Create subject error:", err);
      setFormMessage("");
      showResult(
        "error",
        "บันทึกรายวิชาไม่สำเร็จ",
        err.message || "เกิดข้อผิดพลาดในการบันทึก"
      );
    } finally {
      setSaving(false);
    }
  };

  // Delete Subject
  // Delete Subject - Open Popup
  const handleDelete = (subject) => {
    setConfirmDialog({
      subject,
      title: "ยืนยันการลบรายวิชา",
      message: `ต้องการลบรายวิชา "${subject.code} - ${subject.name}" ใช่หรือไม่?`,
      confirmText: "ยืนยันการลบ",
    });
  };

  // Confirm Delete Subject
  const handleConfirmDelete = async () => {
    if (!confirmDialog?.subject) return;

    const subject = confirmDialog.subject;

    try {
      setActionLoading(true);
      setDeletingId(subject.id);
      setError("");
      setFormMessage("");

      const response = await fetch(
        `${API_BASE_URL}/api/subjects/${subject.id}`,
        {
          method: "DELETE",
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || "ไม่สามารถลบรายวิชาได้");
      }

      setFormMessage("");
      setConfirmDialog(null);

      await fetchData();
      showResult(
        "success",
        "ลบรายวิชาสำเร็จ!",
        `ลบรายวิชา ${subject.code} - ${subject.name} เรียบร้อยแล้ว`
      );
    } catch (err) {
      console.error("Delete subject error:", err);
      setError("");
      setConfirmDialog(null);
      showResult(
        "error",
        "ลบรายวิชาไม่สำเร็จ",
        err.message || "เกิดข้อผิดพลาดในการลบรายวิชา"
      );
    } finally {
      setActionLoading(false);
      setDeletingId(null);
    }
  };

  // Search and pagination for the subject table
  const normalizedSearch = searchTerm.trim().toLocaleLowerCase("th-TH");
  const filteredSubjects = subjects.filter((subject) => {
    if (!normalizedSearch) return true;

    const searchableText = [
      subject.code,
      subject.name,
      subject.section_name,
      formatDays(subject.class_days),
      subject.start_time,
      subject.end_time,
      subject.late_after_minutes,
    ]
      .filter((value) => value !== null && value !== undefined)
      .join(" ")
      .toLocaleLowerCase("th-TH");

    return searchableText.includes(normalizedSearch);
  });

  const totalPages = Math.max(1, Math.ceil(filteredSubjects.length / ITEMS_PER_PAGE));
  const safeCurrentPage = Math.min(currentPage, totalPages);
  const paginatedSubjects = filteredSubjects.slice(
    (safeCurrentPage - 1) * ITEMS_PER_PAGE,
    safeCurrentPage * ITEMS_PER_PAGE
  );

  return (
    <>
      <div className="page-header">
        <h1>รายวิชา</h1>
        <p className="hint">
          กำหนดรายวิชา Section เวลาเรียน และเกณฑ์การมาสาย
        </p>
      </div>

      {/* Import Subject */}
      <div className="card">
        <h2>Import Subject</h2>

        <p className="hint">
          นำเข้ารายวิชาจากไฟล์ Excel (.xlsx)
        </p>

        <form
          className="form-grid"
          onSubmit={handleImport}
        >
          <div className="field full-width">
            <label htmlFor="subject_file">
              ไฟล์ Excel <span style={{ color: "red" }}>*</span>
            </label>

            <input
              type="file"
              id="subject_file"
              name="subject_file"
              accept=".xlsx"
              onChange={handleExcelChange}
              disabled={importing}
              required
            />

            <small className="hint">
              ไฟล์ต้องมีคอลัมน์ code, name, section_id, class_days,
              start_time, end_time และ late_after_minutes
            </small>
          </div>

          <div className="field submit">
            <button
              type="submit"
              disabled={!excelFile || importing}
            >
              {importing ? "กำลัง Import..." : "Import Subject"}
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

      {/* Add Subject */}
      <div className="card">
        <h2>{editingId ? "แก้ไขรายวิชา" : "เพิ่มรายวิชา"}</h2>

        {!loading && sections.length === 0 && (
          <p className="flash error">
            ยังไม่มี Section กรุณาเพิ่ม Section ในเมนู Section ก่อน
          </p>
        )}

        <form className="form-grid" onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="code">
              รหัสวิชา <span style={{ color: "red" }}>*</span>
            </label>

            <input
              type="text"
              id="code"
              name="code"
              placeholder="กรอกรหัสวิชา"
              value={formData.code}
              onChange={handleChange}
              required
            />
          </div>

          <div className="field">
            <label htmlFor="name">
              ชื่อวิชา <span style={{ color: "red" }}>*</span>
            </label>

            <input
              type="text"
              id="name"
              name="name"
              placeholder="ชื่อวิชา"
              value={formData.name}
              onChange={handleChange}
              required
            />
          </div>

          <div className="field full-width">
            <label htmlFor="section_id">
              Section <span style={{ color: "red" }}>*</span>
            </label>

            <select
              id="section_id"
              name="section_id"
              value={formData.section_id}
              onChange={handleChange}
              required
              disabled={loading || sections.length === 0}
            >
              <option value="">-- เลือก Section --</option>

              {sections.map((section) => (
                <option key={section.id} value={section.id}>
                  {section.name}
                </option>
              ))}
            </select>
          </div>

          <div className="field full-width">
            <label>วันเรียน (เลือกได้มากกว่า 1 วัน)</label>

            <div className="days-checkbox">
              {DAYS.map(([value, label]) => (
                <label key={value}>
                  <input
                    type="checkbox"
                    name="class_days"
                    value={value}
                    checked={formData.class_days.includes(value)}
                    onChange={handleDaysChange}
                  />
                  {label}
                </label>
              ))}
            </div>
          </div>

          <div className="field">
            <label htmlFor="start_time">
              เวลาเริ่มเรียน <span style={{ color: "red" }}>*</span>
            </label>

            <input
              type="text"
              id="start_time"
              name="start_time"
              placeholder="เวลาเริ่มเรียน"
              maxLength={5}
              inputMode="numeric"
              autoComplete="off"
              value={formData.start_time}
              onChange={handleTimeChange}
              required
            />

            <small className="hint">
              กรอก 4 หลัก เช่น 0800 จะแสดงเป็น 08:00
            </small>
          </div>

          <div className="field">
            <label htmlFor="end_time">
              เวลาเลิกเรียน <span style={{ color: "red" }}>*</span>
            </label>

            <input
              type="text"
              id="end_time"
              name="end_time"
              placeholder="เวลาเลิกเรียน"
              maxLength={5}
              inputMode="numeric"
              autoComplete="off"
              value={formData.end_time}
              onChange={handleTimeChange}
              required
            />

            <small className="hint">
              กรอก 4 หลัก เช่น 1200 จะแสดงเป็น 12:00
            </small>
          </div>

          <div className="field">
            <label htmlFor="late_after_minutes">
              อนุโลมก่อนถือว่าสาย (นาที)
            </label>

            <input
              type="text"
              id="late_after_minutes"
              name="late_after_minutes"
              inputMode="numeric"
              pattern="[0-9]+"
              maxLength={4}
              value={formData.late_after_minutes}
              onChange={(event) => {
                const value = event.target.value.replace(/\D/g, "");

                setFormData((prev) => ({
                  ...prev,
                  late_after_minutes: value,
                }));
              }}
              required
            />

            <small className="hint">
              กรอกได้เฉพาะตัวเลข 0 ขึ้นไป
            </small>
          </div>

          <div className="field submit button-container">
            <button
              type="submit"
              disabled={saving || loading || sections.length === 0}
            >
              {saving
                ? "กำลังบันทึก..."
                : editingId
                  ? "บันทึกการแก้ไข"
                  : "เพิ่มวิชา"}
            </button>

            {editingId && (
              <button
                type="button"
                className="btn-delete"
                onClick={handleCancelEdit}
                disabled={saving}
              >
                ยกเลิก
              </button>
            )}

            {formMessage && (
              <p className="hint" role="status">
                {formMessage}
              </p>
            )}
          </div>
        </form>
      </div>

      {/* Subject List */}
      <div className="card">
        <h2>รายการวิชา ({filteredSubjects.length})</h2>
        <div className="table-toolbar" style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: "12px", margin: "12px 0" }}>
          <input
            type="search"
            style={{ flex: "1 1 280px", maxWidth: "420px", padding: "10px 12px", border: "1px solid #d1d5db", borderRadius: "8px" }}
            value={searchTerm}
            onChange={(event) => {
              setSearchTerm(event.target.value);
              setCurrentPage(1);
            }}
            placeholder="ค้นหารหัสวิชา ชื่อวิชา Section หรือวันเรียน..."
            aria-label="ค้นหารายวิชา"
          />
          <span className="hint">แสดง {paginatedSubjects.length} จาก {filteredSubjects.length} รายการ</span>
        </div>

        {error && (
          <p className="hint" role="alert">
            {error}
          </p>
        )}

        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>ลำดับ</th>
                <th>รหัสวิชา</th>
                <th>ชื่อวิชา</th>
                <th>Section</th>
                <th>วันเรียน</th>
                <th>เวลาเริ่ม</th>
                <th>เวลาเลิก</th>
                <th>นาทีผ่อนผัน</th>
                <th>จัดการ</th>
              </tr>
            </thead>

            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="9" className="empty-row">
                    กำลังโหลดข้อมูล...
                  </td>
                </tr>
              ) : filteredSubjects.length === 0 ? (
                <tr>
                  <td colSpan="9" className="empty-row">
                    ยังไม่มีข้อมูลรายวิชา
                  </td>
                </tr>
              ) : (
                paginatedSubjects.map((subject, index) => (
                  <tr key={subject.id}>
                    <td data-label="ลำดับ">{(safeCurrentPage - 1) * ITEMS_PER_PAGE + index + 1}</td>
                    <td data-label="รหัสวิชา">{subject.code}</td>
                    <td data-label="ชื่อวิชา">{subject.name}</td>
                    <td data-label="Section">{subject.section_name || "-"}</td>
                    <td data-label="วันเรียน">{formatDays(subject.class_days)}</td>
                    <td data-label="เวลาเริ่ม">{String(subject.start_time || "").slice(0, 5)}</td>
                    <td data-label="เวลาเลิก">{String(subject.end_time || "").slice(0, 5)}</td>
                    <td data-label="นาทีผ่อนผัน">{subject.late_after_minutes ?? 0}</td>

                    <td data-label="จัดการ">
                      <div style={{ display: "flex", gap: "8px" }}>
                        <button
                          type="button"
                          className="btn-edit"
                          onClick={() => handleEdit(subject)}
                          disabled={saving || deletingId === subject.id}
                        >
                          แก้ไข
                        </button>

                        <button
                          type="button"
                          className="btn-delete danger"
                          disabled={deletingId === subject.id || saving}
                          onClick={() => handleDelete(subject)}
                        >
                          {deletingId === subject.id ? "กำลังลบ..." : "ลบ"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        {filteredSubjects.length > 0 && (
          <div className="table-pagination" style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: "12px", marginTop: "16px" }}>
            <span className="hint">หน้า {safeCurrentPage} / {totalPages}</span>
            <div className="table-pagination-actions" style={{ display: "flex", gap: "8px" }}>
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
            className={`confirm-modal ${resultDialog.type === "success" ? "success-modal" : "error-modal"}`}
            onClick={(event) => event.stopPropagation()}
          >
            <div
              className="success-modal-icon"
              style={{
                width: "64px",
                height: "64px",
                margin: "0 auto 16px",
                borderRadius: "50%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: "40px",
                fontWeight: 700,
                lineHeight: 1,
                background: resultDialog.type === "success" ? "#e8f7ee" : "#fdecec",
                color: resultDialog.type === "success" ? "#22a06b" : "#d93025",
              }}
            >
              {resultDialog.type === "success" ? "✓" : "!"}
            </div>

            <h2>{resultDialog.title}</h2>
            <p style={{ whiteSpace: "pre-line" }}>{resultDialog.message}</p>

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

export default Subjects;
