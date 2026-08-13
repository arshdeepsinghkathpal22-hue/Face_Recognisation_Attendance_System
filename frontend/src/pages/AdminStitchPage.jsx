import { useCallback, useMemo } from "react";

import StitchIframe from "@/components/StitchIframe";
import {
  getAdminStudents,
  getAdminTeacherOptions,
  getAdminTeachers,
  registerAdminStudent,
  registerAdminTeacher
} from "@/services/api";
import adminTemplate from "../../stitch_exports/admin_register_biometrics.html?raw";

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function inferBranchFromBatch(batchValue) {
  if (!batchValue) {
    return "CSE";
  }
  const prefix = String(batchValue).split("-")[0]?.trim();
  return prefix || "CSE";
}

function escapeAttribute(value) {
  return escapeHtml(value).replace(/`/g, "&#96;");
}

function hasSignOutText(node) {
  const text = (node?.textContent || "").replace(/\s+/g, " ").trim();
  return /sign\s*out/i.test(text);
}

function getSignOutAction(doc) {
  const interactiveSelector = "button, a, [role='button']";
  const directMatch = [...doc.querySelectorAll(interactiveSelector)].find(hasSignOutText);
  if (directMatch) {
    return directMatch;
  }

  const fallbackMatch = [...doc.querySelectorAll("*")].find((node) => {
    if (!hasSignOutText(node)) {
      return false;
    }

    const className = typeof node.className === "string" ? node.className : "";
    const classBasedPointer = /\bcursor-pointer\b/.test(className);
    const computedCursor = doc.defaultView?.getComputedStyle
      ? doc.defaultView.getComputedStyle(node).cursor
      : "";
    return classBasedPointer || computedCursor === "pointer";
  });

  if (!fallbackMatch) {
    return null;
  }

  return fallbackMatch.closest(`${interactiveSelector}, .cursor-pointer`) || fallbackMatch;
}

export default function AdminStitchPage({ admin, onLogout }) {
  const html = useMemo(() => {
    return adminTemplate.replace(/Administrator/g, escapeHtml(admin?.name || "Administrator"));
  }, [admin?.name]);

  const bindActions = useCallback(
    (doc) => {
      const cleanup = [];

      const nameInput =
        doc.querySelector('input[placeholder*="Arshdeep"]') || doc.querySelectorAll('input[type="text"]')[0];
      const enrollmentInput =
        doc.querySelector('input[placeholder*="99xx"]') || doc.querySelectorAll('input[type="text"]')[1];
      const batchSelect = doc.querySelector("select");

      const browseButton = [...doc.querySelectorAll("button")].find((button) =>
        button.textContent?.includes("Browse Files")
      );
      const registerButton = [...doc.querySelectorAll("button")].find((button) =>
        button.textContent?.includes("Register Profile")
      );
      const signOutAction = getSignOutAction(doc);
      const uploadQueueHeading = [...doc.querySelectorAll("h4")].find((heading) =>
        heading.textContent?.includes("Upload Queue")
      );
      const uploadZoneHeading = [...doc.querySelectorAll("h3")].find((heading) =>
        heading.textContent?.includes("Drag & Drop Image Files")
      );
      const uploadZone = uploadZoneHeading?.closest("div.cursor-pointer");
      const mainContent = doc.querySelector("main.content");

      const teacherPanel = doc.createElement("section");
      teacherPanel.className = "card";
      teacherPanel.style.cssText = "padding: 24px; margin-bottom: 24px;";
      teacherPanel.innerHTML = `
        <div style="display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; flex-wrap: wrap;">
          <div>
            <h3 style="margin: 0 0 6px; font-size: 18px;">Register New Teacher</h3>
            <p class="muted" style="margin: 0; font-size: 13px;">Assign subjects and batches this teacher can take attendance for.</p>
          </div>
        </div>
        <div style="display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-top: 18px;">
          <label>Teacher ID<input data-teacher-field="id" type="text" placeholder="faculty001" /></label>
          <label>Teacher Name<input data-teacher-field="name" type="text" placeholder="Faculty name" /></label>
          <label>Email<input data-teacher-field="email" type="email" placeholder="teacher@example.com" /></label>
          <label>Password<input data-teacher-field="password" type="password" placeholder="Set password" /></label>
        </div>
        <div style="display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 14px; margin-top: 18px; align-items: end;">
          <label>Semester<select data-teacher-field="semester"></select></label>
          <label>Subject<select data-teacher-field="subject"></select></label>
          <label>Batch<select data-teacher-field="batch"></select></label>
          <label>Type<select data-teacher-field="classType"><option value="L">Lecture</option><option value="P">Practical</option></select></label>
          <button class="signout" type="button" data-teacher-action="add" style="height: 44px;">Add Assignment</button>
        </div>
        <div data-teacher-assignments style="display: grid; gap: 10px; margin-top: 16px;"></div>
        <p data-teacher-status class="muted" style="margin: 14px 0 0; font-size: 12px; font-weight: 700;">Load ho raha hai...</p>
        <div style="margin-top: 16px;">
          <button class="signout" type="button" data-teacher-action="register">Register Teacher</button>
        </div>
      `;
      if (mainContent) {
        const firstGrid = mainContent.querySelector('div[style*="grid-template-columns"]');
        mainContent.insertBefore(teacherPanel, firstGrid || mainContent.firstChild);
      }

      const directoryPanel = doc.createElement("section");
      directoryPanel.className = "card";
      directoryPanel.style.cssText = "padding: 24px; margin-bottom: 24px;";
      directoryPanel.innerHTML = `
        <div style="display: flex; justify-content: space-between; gap: 16px; align-items: center; flex-wrap: wrap;">
          <div>
            <h3 style="margin: 0 0 6px; font-size: 18px;">Saved Records & Reports</h3>
            <p class="muted" style="margin: 0; font-size: 13px;">Persisted teachers, students, and attendance reports.</p>
          </div>
          <div style="display: flex; gap: 10px;">
            <button class="signout" type="button" data-admin-action="export-csv" style="background: #2563eb;">Export CSV Report</button>
            <button class="signout" type="button" data-directory-action="refresh">Refresh</button>
          </div>
        </div>
        <div style="display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; margin-top: 18px;">
          <div>
            <h4 style="margin: 0 0 10px; font-size: 14px;">Teachers</h4>
            <div data-directory-teachers style="display: grid; gap: 8px;"></div>
          </div>
          <div>
            <h4 style="margin: 0 0 10px; font-size: 14px;">Students</h4>
            <div data-directory-students style="display: grid; gap: 8px;"></div>
          </div>
        </div>
      `;
      if (mainContent) {
        teacherPanel.insertAdjacentElement("afterend", directoryPanel);
      }

      const teacherIdInput = teacherPanel.querySelector('[data-teacher-field="id"]');
      const teacherNameInput = teacherPanel.querySelector('[data-teacher-field="name"]');
      const teacherEmailInput = teacherPanel.querySelector('[data-teacher-field="email"]');
      const teacherPasswordInput = teacherPanel.querySelector('[data-teacher-field="password"]');
      const teacherSemesterSelect = teacherPanel.querySelector('[data-teacher-field="semester"]');
      const teacherSubjectSelect = teacherPanel.querySelector('[data-teacher-field="subject"]');
      const teacherBatchSelect = teacherPanel.querySelector('[data-teacher-field="batch"]');
      const teacherClassTypeSelect = teacherPanel.querySelector('[data-teacher-field="classType"]');
      const teacherAssignmentsList = teacherPanel.querySelector("[data-teacher-assignments]");
      const teacherStatus = teacherPanel.querySelector("[data-teacher-status]");
      const addTeacherAssignmentButton = teacherPanel.querySelector('[data-teacher-action="add"]');
      const registerTeacherButton = teacherPanel.querySelector('[data-teacher-action="register"]');

      let teacherOptions = { semesters: [], batches: [] };
      let teacherAssignments = [];

      const directoryTeachers = directoryPanel.querySelector("[data-directory-teachers]");
      const directoryStudents = directoryPanel.querySelector("[data-directory-students]");
      const refreshDirectoryButton = directoryPanel.querySelector('[data-directory-action="refresh"]');

      const renderDirectoryList = (container, items, emptyMessage, renderItem) => {
        if (!container) {
          return;
        }
        if (!items.length) {
          container.innerHTML = `<div style="padding: 12px; border: 1px solid #e5e7eb; border-radius: 8px; color: #6b7280; font-size: 12px; font-weight: 700;">${escapeHtml(emptyMessage)}</div>`;
          return;
        }
        container.innerHTML = items.map(renderItem).join("");
      };

      const loadDirectory = async () => {
        try {
          const [teachersResponse, studentsResponse] = await Promise.all([
            getAdminTeachers(),
            getAdminStudents()
          ]);
          renderDirectoryList(
            directoryTeachers,
            teachersResponse.items || [],
            "No teachers saved yet.",
            (teacher) => `
              <div style="padding: 12px; border: 1px solid #e5e7eb; border-radius: 8px; background: #f8fafc;">
                <div style="font-size: 13px; font-weight: 900;">${escapeHtml(teacher.name)}</div>
                <div style="font-size: 12px; color: #475569;">${escapeHtml(teacher.teacher_id)}${teacher.email ? ` - ${escapeHtml(teacher.email)}` : ""}</div>
              </div>
            `
          );
          renderDirectoryList(
            directoryStudents,
            studentsResponse.items || [],
            "No students saved yet.",
            (student) => `
              <div style="padding: 12px; border: 1px solid #e5e7eb; border-radius: 8px; background: #f8fafc;">
                <div style="font-size: 13px; font-weight: 900;">${escapeHtml(student.name)}</div>
                <div style="font-size: 12px; color: #475569;">${escapeHtml(student.student_id)} - ${escapeHtml(student.batch || student.branch || "-")}</div>
              </div>
            `
          );
        } catch (apiError) {
          renderDirectoryList(directoryTeachers, [], apiError.message || "Failed to load teachers.", () => "");
          renderDirectoryList(directoryStudents, [], apiError.message || "Failed to load students.", () => "");
        }
      };
      void loadDirectory();

      const exportCsvButton = directoryPanel.querySelector('[data-admin-action="export-csv"]');
      if (exportCsvButton) {
        const handleExportCsv = (event) => {
          event.preventDefault();
          window.open("/api/admin/reports/csv", "_blank");
        };
        exportCsvButton.addEventListener("click", handleExportCsv);
        cleanup.push(() => exportCsvButton.removeEventListener("click", handleExportCsv));
      }

      if (refreshDirectoryButton) {
        const handleRefreshDirectory = (event) => {
          event.preventDefault();
          void loadDirectory();
        };
        refreshDirectoryButton.addEventListener("click", handleRefreshDirectory);
        cleanup.push(() => refreshDirectoryButton.removeEventListener("click", handleRefreshDirectory));
      }

      const setTeacherStatus = (message, type = "neutral") => {
        if (!teacherStatus) {
          return;
        }
        teacherStatus.textContent = message;
        teacherStatus.style.color =
          type === "error" ? "#b91c1c" : type === "success" ? "#047857" : "#6b7280";
      };

      const selectedSemester = () =>
        teacherOptions.semesters.find((semester) => semester.id === teacherSemesterSelect?.value) ||
        teacherOptions.semesters[0] ||
        null;

      const renderTeacherSubjects = () => {
        const semester = selectedSemester();
        if (!teacherSubjectSelect) {
          return;
        }
        teacherSubjectSelect.innerHTML = (semester?.subjects || [])
          .map((subject) => `<option value="${escapeAttribute(subject.id)}">${escapeHtml(subject.name)}</option>`)
          .join("");
      };

      const renderTeacherOptions = () => {
        if (teacherSemesterSelect) {
          teacherSemesterSelect.innerHTML = teacherOptions.semesters
            .map((semester) => `<option value="${escapeAttribute(semester.id)}">${escapeHtml(semester.label)}</option>`)
            .join("");
        }
        if (teacherBatchSelect) {
          const batches = teacherOptions.batches.length ? teacherOptions.batches : ["CSE"];
          teacherBatchSelect.innerHTML = batches
            .map((batch) => `<option value="${escapeAttribute(batch)}">${escapeHtml(batch)}</option>`)
            .join("");
        }
        renderTeacherSubjects();
      };

      const renderTeacherAssignments = () => {
        if (!teacherAssignmentsList) {
          return;
        }
        if (!teacherAssignments.length) {
          teacherAssignmentsList.innerHTML =
            '<div style="padding: 12px 14px; border: 1px solid #e5e7eb; border-radius: 8px; color: #6b7280; font-size: 13px; font-weight: 700;">No assignments added yet.</div>';
          return;
        }
        teacherAssignmentsList.innerHTML = teacherAssignments
          .map(
            (item, index) => `
              <div style="display: flex; justify-content: space-between; gap: 12px; align-items: center; padding: 12px 14px; border: 1px solid #e5e7eb; border-radius: 8px; background: #f8fafc;">
                <span style="font-size: 13px; font-weight: 800;">${escapeHtml(item.subjectName)} - ${escapeHtml(item.batch)} - ${escapeHtml(item.semesterLabel)} (${escapeHtml(item.classType)})</span>
                <button type="button" data-remove-assignment="${index}" style="background: transparent; color: #be123c; font-size: 12px; font-weight: 900;">Remove</button>
              </div>
            `
          )
          .join("");
        teacherAssignmentsList.querySelectorAll("[data-remove-assignment]").forEach((button) => {
          const removeHandler = (event) => {
            event.preventDefault();
            const index = Number(button.getAttribute("data-remove-assignment"));
            teacherAssignments = teacherAssignments.filter((_, itemIndex) => itemIndex !== index);
            renderTeacherAssignments();
          };
          button.addEventListener("click", removeHandler, { once: true });
        });
      };

      const loadTeacherOptions = async () => {
        try {
          teacherOptions = await getAdminTeacherOptions();
          renderTeacherOptions();
          renderTeacherAssignments();
          setTeacherStatus("Ready to register a teacher.");
        } catch (apiError) {
          setTeacherStatus(apiError.message || "Failed to load teacher options.", "error");
        }
      };
      void loadTeacherOptions();

      if (teacherSemesterSelect) {
        const handleSemesterChange = () => {
          renderTeacherSubjects();
        };
        teacherSemesterSelect.addEventListener("change", handleSemesterChange);
        cleanup.push(() => teacherSemesterSelect.removeEventListener("change", handleSemesterChange));
      }

      if (addTeacherAssignmentButton) {
        const handleAddTeacherAssignment = (event) => {
          event.preventDefault();
          const semester = selectedSemester();
          const subject = (semester?.subjects || []).find((item) => item.id === teacherSubjectSelect?.value);
          const batch = teacherBatchSelect?.value?.trim() || "";
          const classType = teacherClassTypeSelect?.value || "L";

          if (!semester || !subject || !batch) {
            setTeacherStatus("Semester, subject, and batch are required.", "error");
            return;
          }

          const duplicate = teacherAssignments.some(
            (item) =>
              item.semesterId === semester.id &&
              item.subjectId === subject.id &&
              item.batch === batch &&
              item.classType === classType
          );
          if (duplicate) {
            setTeacherStatus("This assignment is already added.", "error");
            return;
          }

          teacherAssignments = [
            ...teacherAssignments,
            {
              semesterId: semester.id,
              semesterLabel: semester.label,
              subjectId: subject.id,
              subjectName: subject.name,
              batch,
              classType
            }
          ];
          renderTeacherAssignments();
          setTeacherStatus("Assignment added. Register teacher to save.");
        };
        addTeacherAssignmentButton.addEventListener("click", handleAddTeacherAssignment);
        cleanup.push(() => addTeacherAssignmentButton.removeEventListener("click", handleAddTeacherAssignment));
      }

      if (registerTeacherButton) {
        const handleRegisterTeacher = async (event) => {
          event.preventDefault();
          const teacherId = teacherIdInput?.value?.trim() || "";
          const teacherName = teacherNameInput?.value?.trim() || "";
          const teacherEmail = teacherEmailInput?.value?.trim() || "";
          const teacherPassword = teacherPasswordInput?.value?.trim() || "";

          if (!teacherId || !teacherName || !teacherEmail || !teacherPassword) {
            setTeacherStatus("Teacher ID, name, email, and password are required.", "error");
            return;
          }
          if (!teacherAssignments.length) {
            setTeacherStatus("Add at least one assignment.", "error");
            return;
          }

          registerTeacherButton.disabled = true;
          setTeacherStatus("Registering teacher...");
          try {
            const response = await registerAdminTeacher({
              teacher_id: teacherId,
              name: teacherName,
              email: teacherEmail,
              password: teacherPassword,
              assignments: teacherAssignments.map((item) => ({
                semester_id: item.semesterId,
                subject_id: item.subjectId,
                batch: item.batch,
                class_type: item.classType
              }))
            });

            setTeacherStatus(
              `Registered ${response.teacher.name} with ${response.assignments.length} assignment(s).`,
              "success"
            );
            if (teacherIdInput) {
              teacherIdInput.value = "";
            }
            if (teacherNameInput) {
              teacherNameInput.value = "";
            }
            if (teacherPasswordInput) {
              teacherPasswordInput.value = "";
            }
            if (teacherEmailInput) {
              teacherEmailInput.value = "";
            }
            teacherAssignments = [];
            renderTeacherAssignments();
            void loadDirectory();
          } catch (apiError) {
            setTeacherStatus(apiError.message || "Teacher registration failed.", "error");
          } finally {
            registerTeacherButton.disabled = false;
          }
        };
        registerTeacherButton.addEventListener("click", handleRegisterTeacher);
        cleanup.push(() => registerTeacherButton.removeEventListener("click", handleRegisterTeacher));
      }

      const statusText = doc.createElement("p");
      statusText.className = "mt-4 text-xs font-semibold text-on-surface-variant";
      statusText.textContent = "Ready to register a new profile.";
      registerButton?.parentElement?.insertBefore(statusText, registerButton.parentElement.firstChild);

      let selectedFiles = [];
      const minUploads = 5;
      const maxUploads = 15;
      const fileInput = doc.createElement("input");
      fileInput.type = "file";
      fileInput.accept = "image/*";
      fileInput.multiple = true;
      fileInput.style.display = "none";
      doc.body.appendChild(fileInput);

      const liveCaptureButton = doc.createElement("button");
      liveCaptureButton.type = "button";
      liveCaptureButton.className = "signout";
      liveCaptureButton.style.cssText =
        "background: #0e7490; color: #ffffff; padding: 11px 16px; border-radius: 8px; font-size: 12px; font-weight: 850; cursor: pointer; border: 0; display: inline-flex; align-items: center; gap: 8px; margin-left: 10px; box-shadow: 0 4px 12px rgba(14, 116, 144, 0.25); transition: background 0.15s ease;";
      liveCaptureButton.innerHTML =
        '<span style="font-size: 14px;">📷</span><span>Live Photo</span>';
      liveCaptureButton.onmouseenter = () => {
        liveCaptureButton.style.background = "#0891b2";
      };
      liveCaptureButton.onmouseleave = () => {
        liveCaptureButton.style.background = "#0e7490";
      };

      const queueDetails = doc.createElement("div");
      queueDetails.style.cssText = "display: grid; gap: 8px; margin-top: 12px;";

      const cameraModal = doc.createElement("div");
      cameraModal.style.cssText =
        "position: fixed; top: 0; left: 0; right: 0; bottom: 0; z-index: 99999; display: none; align-items: center; justify-content: center; background: rgba(0, 0, 0, 0.75); padding: 16px; backdrop-filter: blur(4px);";
      cameraModal.innerHTML = `
        <div style="width: 100%; max-width: 640px; background: #ffffff; border-radius: 12px; padding: 20px; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.3); font-family: Inter, Arial, sans-serif;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
            <h3 style="margin: 0; font-size: 16px; font-weight: 800; color: #111827;">Live Camera Capture</h3>
            <button type="button" data-action="close" style="background: #f3f4f6; color: #374151; padding: 6px 14px; border-radius: 6px; font-size: 12px; font-weight: 700; cursor: pointer; border: 0;">Close</button>
          </div>
          
          <div data-modal="status" style="margin-bottom: 10px; font-size: 12px; font-weight: 700; color: #374151; padding: 8px 12px; border-radius: 6px; background: #f9fafb; border: 1px solid #e5e7eb;">
            Starting camera...
          </div>

          <div style="position: relative; width: 100%; height: 380px; background: #000000; border-radius: 8px; overflow: hidden; display: flex; align-items: center; justify-content: center;">
            <video autoplay playsinline muted style="width: 100%; height: 100%; object-fit: cover; display: block; background: #000000;"></video>
            <canvas style="display: none;"></canvas>
          </div>

          <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 14px;">
            <span style="font-size: 12px; font-weight: 700; color: #4b5563;">Queue: <span data-action="queue-count">0</span> / 15</span>
            <button type="button" data-action="capture" disabled style="background: #111827; color: #ffffff; padding: 10px 22px; border-radius: 8px; font-size: 13px; font-weight: 800; cursor: not-allowed; opacity: 0.5; border: 0; transition: all 0.2s ease;">Capture Photo</button>
          </div>
        </div>
      `;
      doc.body.appendChild(cameraModal);

      const modalStatus = cameraModal.querySelector('[data-modal="status"]');
      const cameraVideo = cameraModal.querySelector("video");
      const cameraCanvas = cameraModal.querySelector("canvas");
      const closeCameraButton = cameraModal.querySelector('[data-action="close"]');
      const captureCameraButton = cameraModal.querySelector('[data-action="capture"]');
      const queueCount = cameraModal.querySelector('[data-action="queue-count"]');

      let cameraStream = null;

      const setModalStatus = (msg, isError = false) => {
        if (!modalStatus) return;
        modalStatus.textContent = msg;
        if (isError) {
          modalStatus.style.color = "#991b1b";
          modalStatus.style.background = "#fef2f2";
          modalStatus.style.borderColor = "#fecaca";
        } else {
          modalStatus.style.color = "#065f46";
          modalStatus.style.background = "#ecfdf5";
          modalStatus.style.borderColor = "#a7f3d0";
        }
      };

      let validationResults = [];

      const updateUploadQueue = () => {
        const validCount = validationResults.length
          ? validationResults.filter((r) => r.accepted).length
          : selectedFiles.length;

        if (uploadQueueHeading) {
          uploadQueueHeading.textContent = `Upload Queue (${selectedFiles.length}/${maxUploads})`;
        }
        if (queueCount) {
          queueCount.textContent = String(selectedFiles.length);
        }

        if (queueDetails) {
          if (!selectedFiles.length) {
            queueDetails.innerHTML = `<div style="border: 1px dashed #cbd5e1; border-radius: 8px; padding: 12px; color: #64748b; font-size: 12px; font-weight: 700;">Add ${minUploads}-${maxUploads} clear face images. Low-light photos are automatically enhanced.</div>`;
            return;
          }

          const hasFailures = validationResults.some((r) => !r.accepted);

          const headerBadgeMarkup = `
            <div style="display: flex; items-center; justify-content: space-between; gap: 10px; margin-bottom: 8px; padding: 8px 12px; border-radius: 8px; background: #f1f5f9; border: 1px solid #cbd5e1;">
              <span style="font-size: 12px; font-weight: 800; color: #1e293b;">
                Valid photos: <strong style="color: ${validCount >= minUploads ? "#15803d" : "#b91c1c"};">${validCount}</strong> / ${maxUploads} (Required: ${minUploads}–${maxUploads})
              </span>
              ${
                hasFailures
                  ? '<button type="button" data-action="remove-failed" style="font-size: 11px; font-weight: 800; color: #be123c; background: #ffe4e6; border: 1px solid #fecdd3; border-radius: 6px; padding: 3px 8px;">Remove Failed Images</button>'
                  : ""
              }
            </div>
          `;

          const itemsMarkup = selectedFiles
            .map((file, index) => {
              const res = validationResults.find((r) => r.filename === file.name);
              const accepted = res ? res.accepted : null;
              const msg = res ? res.message : "Pending submission";

              let badgeStyle = "background: #f8fafc; border-color: #e5e7eb; color: #475569;";
              let icon = "📷";
              if (accepted === true) {
                badgeStyle = "background: #f0fdf4; border-color: #bbf7d0; color: #166534;";
                icon = "✓ Accepted";
              } else if (accepted === false) {
                badgeStyle = "background: #fef2f2; border-color: #fecaca; color: #991b1b;";
                icon = "✗ Rejected";
              }

              return `
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px; border: 1px solid; border-radius: 8px; padding: 8px 12px; ${badgeStyle}">
                  <div style="min-width: 0; flex: 1;">
                    <div style="font-size: 12px; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(file.name || `Image ${index + 1}`)}</div>
                    <div style="font-size: 11px; font-weight: 600; opacity: 0.9;">${accepted !== null ? `${icon} — ${escapeHtml(msg)}` : "Queued"}</div>
                  </div>
                  <button type="button" data-remove-image="${index}" style="flex: 0 0 auto; color: #be123c; font-size: 12px; font-weight: 900; background: transparent;">Delete</button>
                </div>
              `;
            })
            .join("");

          queueDetails.innerHTML = `${headerBadgeMarkup}${itemsMarkup}`;

          const removeFailedBtn = queueDetails.querySelector('[data-action="remove-failed"]');
          if (removeFailedBtn) {
            const handleRemoveFailed = (event) => {
              event.preventDefault();
              const failedNames = new Set(
                validationResults.filter((r) => !r.accepted).map((r) => r.filename)
              );
              selectedFiles = selectedFiles.filter((file) => !failedNames.has(file.name));
              validationResults = validationResults.filter((r) => r.accepted);
              updateUploadQueue();
              setStatus("Removed failed images from queue. Add replacements if needed.");
            };
            removeFailedBtn.addEventListener("click", handleRemoveFailed, { once: true });
          }

          queueDetails.querySelectorAll("[data-remove-image]").forEach((button) => {
            const removeHandler = (event) => {
              event.preventDefault();
              const index = Number(button.getAttribute("data-remove-image"));
              const removedFile = selectedFiles[index];
              selectedFiles = selectedFiles.filter((_, itemIndex) => itemIndex !== index);
              if (removedFile) {
                validationResults = validationResults.filter((r) => r.filename !== removedFile.name);
              }
              updateUploadQueue();
              setStatus("Image removed. Add a replacement if needed.");
            };
            button.addEventListener("click", removeHandler, { once: true });
          });
        }
      };

      const setStatus = (message, type = "neutral") => {
        statusText.textContent = message;
        if (type === "error") {
          statusText.className = "mt-4 text-xs font-semibold text-red-700";
        } else if (type === "success") {
          statusText.className = "mt-4 text-xs font-semibold text-emerald-700";
        } else {
          statusText.className = "mt-4 text-xs font-semibold text-on-surface-variant";
        }
      };

      const addFilesToQueue = (incomingFiles, sourceLabel) => {
        const files = Array.from(incomingFiles || []);
        if (files.length === 0) {
          return;
        }

        const remaining = maxUploads - selectedFiles.length;
        if (remaining <= 0) {
          setStatus(`Upload queue is full (${maxUploads}/${maxUploads}).`, "error");
          return;
        }

        const accepted = files.slice(0, remaining);
        const skipped = files.length - accepted.length;
        selectedFiles = [...selectedFiles, ...accepted];
        updateUploadQueue();

        const baseMessage = `${accepted.length} image(s) added from ${sourceLabel}.`;
        if (skipped > 0) {
          setStatus(`${baseMessage} ${skipped} skipped due to upload limit (${maxUploads}).`, "error");
        } else {
          setStatus(baseMessage);
        }
      };

      const stopCameraStream = () => {
        if (cameraStream) {
          cameraStream.getTracks().forEach((track) => track.stop());
          cameraStream = null;
        }
        if (cameraVideo) {
          cameraVideo.srcObject = null;
        }
        if (captureCameraButton) {
          captureCameraButton.disabled = true;
          captureCameraButton.style.opacity = "0.5";
          captureCameraButton.style.cursor = "not-allowed";
        }
      };

      const closeCameraModal = () => {
        cameraModal.style.display = "none";
        stopCameraStream();
      };

      const openCameraModal = async () => {
        console.log("CAMERA BUTTON CLICKED");
        if (selectedFiles.length >= maxUploads) {
          setStatus(`Upload queue is full (${maxUploads}/${maxUploads}).`, "error");
          return;
        }

        const nav = doc.defaultView?.navigator || window.navigator;
        if (!nav?.mediaDevices?.getUserMedia) {
          console.error("CAMERA ERROR: navigator.mediaDevices is undefined or getUserMedia not supported");
          setStatus("Camera access requires a secure localhost/HTTPS context.", "error");
          return;
        }

        if (captureCameraButton) {
          captureCameraButton.disabled = true;
          captureCameraButton.style.opacity = "0.5";
          captureCameraButton.style.cursor = "not-allowed";
        }

        cameraModal.style.display = "flex";
        setModalStatus("Requesting camera permission...");

        console.log("REQUESTING CAMERA");
        try {
          cameraStream = await nav.mediaDevices.getUserMedia({
            video: { facingMode: "user" },
            audio: false
          });
          console.log("STREAM RECEIVED", cameraStream);

          if (!cameraVideo) {
            console.error("CAMERA ERROR: Video element does not exist");
            setModalStatus("Video element missing", true);
            return;
          }

          console.log("VIDEO REF READY", cameraVideo);
          cameraVideo.srcObject = cameraStream;
          console.log("STREAM ASSIGNED");

          await cameraVideo.play().catch((playErr) => {
            console.warn("Video play error (will retry):", playErr);
          });
          console.log("VIDEO PLAYING");
          console.log("CAMERA STARTED");

          if (captureCameraButton) {
            captureCameraButton.disabled = false;
            captureCameraButton.style.opacity = "1";
            captureCameraButton.style.cursor = "pointer";
          }
          setModalStatus("Camera active. Click Capture Photo to add images.");
        } catch (error) {
          console.error("CAMERA ERROR:", error);
          stopCameraStream();

          const errName = error?.name || "";
          let userMsg = `Camera error: ${error?.message || error}`;
          if (errName === "NotAllowedError" || errName === "PermissionDeniedError") {
            userMsg = "Camera permission denied. Please allow camera access in your browser.";
          } else if (errName === "NotFoundError" || errName === "DevicesNotFoundError") {
            userMsg = "No camera found.";
          } else if (errName === "NotReadableError" || errName === "TrackStartError") {
            userMsg = "Camera is currently in use by another application.";
          } else if (errName === "SecurityError") {
            userMsg = "Camera access requires a secure localhost/HTTPS context.";
          }

          setModalStatus(userMsg, true);
        }
      };

      const capturePhotoFromCamera = () => {
        if (!cameraVideo || !cameraCanvas) {
          console.error("CAMERA ERROR: Missing video or canvas element for capture");
          return;
        }

        if (selectedFiles.length >= maxUploads) {
          setStatus(`Upload queue is full (${maxUploads}/${maxUploads}).`, "error");
          closeCameraModal();
          return;
        }

        const width = cameraVideo.videoWidth || 640;
        const height = cameraVideo.videoHeight || 480;
        if (!width || !height) {
          setModalStatus("Camera is warming up. Please wait a moment...", true);
          return;
        }

        cameraCanvas.width = width;
        cameraCanvas.height = height;
        const context = cameraCanvas.getContext("2d");
        if (!context) {
          setModalStatus("Failed to capture frame context.", true);
          return;
        }

        context.drawImage(cameraVideo, 0, 0, width, height);
        cameraCanvas.toBlob(
          (blob) => {
            if (!blob) {
              setModalStatus("Failed to create image blob.", true);
              return;
            }

            const timestamp = new Date().toISOString().replace(/[.:]/g, "-");
            const capturedFile = new File([blob], `live_${timestamp}.jpg`, { type: "image/jpeg" });
            addFilesToQueue([capturedFile], "live camera");
            setModalStatus(`Photo captured! Total in queue: ${selectedFiles.length}/${maxUploads}`);

            if (selectedFiles.length >= maxUploads) {
              closeCameraModal();
            }
          },
          "image/jpeg",
          0.92
        );
      };

      const handleFileChange = () => {
        addFilesToQueue(fileInput.files, "file picker");
        fileInput.value = "";
      };

      fileInput.addEventListener("change", handleFileChange);
      cleanup.push(() => fileInput.removeEventListener("change", handleFileChange));

      if (browseButton?.parentElement) {
        browseButton.insertAdjacentElement("afterend", liveCaptureButton);
        liveCaptureButton.insertAdjacentElement("afterend", queueDetails);
      }
      updateUploadQueue();

      const handleOpenCamera = (event) => {
        event.preventDefault();
        event.stopPropagation();
        void openCameraModal();
      };
      liveCaptureButton.addEventListener("click", handleOpenCamera);
      cleanup.push(() => liveCaptureButton.removeEventListener("click", handleOpenCamera));

      if (closeCameraButton) {
        const handleCloseCamera = (event) => {
          event.preventDefault();
          closeCameraModal();
        };
        closeCameraButton.addEventListener("click", handleCloseCamera);
        cleanup.push(() => closeCameraButton.removeEventListener("click", handleCloseCamera));
      }

      if (captureCameraButton) {
        const handleCaptureCamera = (event) => {
          event.preventDefault();
          capturePhotoFromCamera();
        };
        captureCameraButton.addEventListener("click", handleCaptureCamera);
        cleanup.push(() => captureCameraButton.removeEventListener("click", handleCaptureCamera));
      }

      const handleCameraBackdrop = (event) => {
        if (event.target === cameraModal) {
          closeCameraModal();
        }
      };
      cameraModal.addEventListener("click", handleCameraBackdrop);
      cleanup.push(() => cameraModal.removeEventListener("click", handleCameraBackdrop));

      if (browseButton) {
        const handleBrowse = (event) => {
          event.preventDefault();
          event.stopPropagation();
          fileInput.click();
        };
        browseButton.addEventListener("click", handleBrowse);
        cleanup.push(() => browseButton.removeEventListener("click", handleBrowse));
      }

      if (uploadZone) {
        const handleZoneClick = (event) => {
          if (event.target?.closest?.("button, input, select, textarea, a, label")) {
            return;
          }
          fileInput.click();
        };
        uploadZone.addEventListener("click", handleZoneClick);
        cleanup.push(() => uploadZone.removeEventListener("click", handleZoneClick));
      }

      if (registerButton) {
        const handleRegister = async (event) => {
          event.preventDefault();

          const studentName = nameInput?.value?.trim() || "";
          const studentId = enrollmentInput?.value?.trim() || "";
          const batch = batchSelect?.value?.trim() || "";

          if (!studentName || !studentId) {
            setStatus("Student name and enrollment number are required.", "error");
            return;
          }
          if (!batch) {
            setStatus("Please select a batch.", "error");
            return;
          }
          if (selectedFiles.length < minUploads) {
            setStatus(`Upload or capture at least ${minUploads} clear face images before registering.`, "error");
            return;
          }

          registerButton.disabled = true;
          setStatus("Processing face encodings & validating images...", "neutral");

          try {
            const branch = inferBranchFromBatch(batch);
            const response = await registerAdminStudent({
              student_id: studentId,
              name: studentName,
              branch,
              batch,
              images: selectedFiles
            });

            validationResults = response.results || [];
            setStatus(
              `Registered ${response.student.name} (${response.student.student_id}) with ${response.valid_images}/${response.uploaded_images} valid image(s).`,
              "success"
            );

            if (nameInput) {
              nameInput.value = "";
            }
            if (enrollmentInput) {
              enrollmentInput.value = "";
            }
            if (batchSelect) {
              batchSelect.value = "";
            }
            fileInput.value = "";
            selectedFiles = [];
            validationResults = [];
            updateUploadQueue();
            void loadDirectory();
          } catch (apiError) {
            const results = apiError.detail?.results || [];
            if (results.length) {
              validationResults = results;
              updateUploadQueue();
            }
            const validCount = results.filter((r) => r.accepted).length;
            const message = apiError.detail?.message || apiError.message || "Registration failed.";
            if (results.length) {
              setStatus(`${message} (${validCount}/${selectedFiles.length} passed). Keep valid images and click 'Remove Failed Images' or add more.`, "error");
            } else {
              setStatus(message, "error");
            }
          } finally {
            registerButton.disabled = false;
          }
        };

        registerButton.addEventListener("click", handleRegister);
        cleanup.push(() => registerButton.removeEventListener("click", handleRegister));
      }

      if (signOutAction) {
        const handleSignOut = (event) => {
          event.preventDefault();
          void onLogout();
        };
        signOutAction.addEventListener("click", handleSignOut);
        cleanup.push(() => signOutAction.removeEventListener("click", handleSignOut));
      }

      return () => {
        closeCameraModal();
        cleanup.forEach((dispose) => dispose());
        fileInput.remove();
        liveCaptureButton.remove();
        cameraModal.remove();
        teacherPanel.remove();
        directoryPanel.remove();
      };
    },
    [onLogout]
  );

  return (
    <div className="relative h-screen w-full bg-white">
      <StitchIframe html={html} title="Admin Biometrics Registration" allow="camera *" onBind={bindActions} />
    </div>
  );
}
