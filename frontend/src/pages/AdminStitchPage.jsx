import { useCallback, useMemo } from "react";

import StitchIframe from "@/components/StitchIframe";
import { getAdminTeacherOptions, registerAdminStudent, registerAdminTeacher } from "@/services/api";
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
        <div style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; margin-top: 18px;">
          <label>Teacher ID<input data-teacher-field="id" type="text" placeholder="faculty001" /></label>
          <label>Teacher Name<input data-teacher-field="name" type="text" placeholder="Faculty name" /></label>
          <label>Password<input data-teacher-field="password" type="text" placeholder="Set password" /></label>
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

      const teacherIdInput = teacherPanel.querySelector('[data-teacher-field="id"]');
      const teacherNameInput = teacherPanel.querySelector('[data-teacher-field="name"]');
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
          const teacherPassword = teacherPasswordInput?.value?.trim() || "";

          if (!teacherId || !teacherName || !teacherPassword) {
            setTeacherStatus("Teacher ID, name, and password are required.", "error");
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
            teacherAssignments = [];
            renderTeacherAssignments();
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
      const maxUploads = 10;
      const fileInput = doc.createElement("input");
      fileInput.type = "file";
      fileInput.accept = "image/*";
      fileInput.multiple = true;
      fileInput.style.display = "none";
      doc.body.appendChild(fileInput);

      const liveCaptureButton = doc.createElement("button");
      liveCaptureButton.type = "button";
      liveCaptureButton.className =
        "mt-3 border border-outline-variant/40 bg-surface-container-high text-primary font-body text-sm font-medium py-3 px-8 rounded-DEFAULT hover:bg-surface-container-highest transition-colors flex items-center gap-2";
      liveCaptureButton.innerHTML =
        '<span class="material-symbols-outlined text-sm">photo_camera</span><span>Capture Live Photo</span>';

      const cameraModal = doc.createElement("div");
      cameraModal.className = "fixed inset-0 z-[1000] hidden items-center justify-center bg-black/70 p-4";
      cameraModal.innerHTML = `
        <div class="w-full max-w-2xl rounded-lg bg-white p-4 shadow-2xl">
          <div class="mb-3 flex items-center justify-between">
            <h3 class="text-sm font-bold text-gray-900">Live Camera Capture</h3>
            <button type="button" data-action="close" class="rounded bg-gray-100 px-3 py-1 text-xs font-semibold text-gray-700 hover:bg-gray-200">Close</button>
          </div>
          <div class="overflow-hidden rounded bg-black">
            <video autoplay playsinline class="h-[420px] w-full object-cover"></video>
            <canvas class="hidden"></canvas>
          </div>
          <div class="mt-3 flex items-center justify-between">
            <p class="text-xs text-gray-600">Queue: <span data-action="queue-count">0</span>/10</p>
            <button type="button" data-action="capture" class="rounded bg-black px-4 py-2 text-xs font-semibold text-white hover:bg-gray-800">Capture Photo</button>
          </div>
        </div>
      `;
      doc.body.appendChild(cameraModal);

      const cameraVideo = cameraModal.querySelector("video");
      const cameraCanvas = cameraModal.querySelector("canvas");
      const closeCameraButton = cameraModal.querySelector('[data-action="close"]');
      const captureCameraButton = cameraModal.querySelector('[data-action="capture"]');
      const queueCount = cameraModal.querySelector('[data-action="queue-count"]');

      let cameraStream = null;

      const updateUploadQueue = () => {
        if (uploadQueueHeading) {
          uploadQueueHeading.textContent = `Upload Queue (${selectedFiles.length}/${maxUploads})`;
        }
        if (queueCount) {
          queueCount.textContent = String(selectedFiles.length);
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
      };

      const closeCameraModal = () => {
        cameraModal.classList.add("hidden");
        cameraModal.classList.remove("flex");
        stopCameraStream();
      };

      const openCameraModal = async () => {
        if (selectedFiles.length >= maxUploads) {
          setStatus(`Upload queue is full (${maxUploads}/${maxUploads}).`, "error");
          return;
        }

        if (!doc.defaultView?.navigator?.mediaDevices?.getUserMedia) {
          setStatus("Live camera capture is not supported in this browser.", "error");
          return;
        }

        cameraModal.classList.remove("hidden");
        cameraModal.classList.add("flex");

        try {
          cameraStream = await doc.defaultView.navigator.mediaDevices.getUserMedia({
            video: { facingMode: "user" },
            audio: false
          });
          if (cameraVideo) {
            cameraVideo.srcObject = cameraStream;
            await cameraVideo.play();
          }
          setStatus("Camera ready. Click Capture Photo to add images.");
        } catch (_error) {
          closeCameraModal();
          setStatus("Unable to access camera. Please allow camera permission.", "error");
        }
      };

      const capturePhotoFromCamera = () => {
        if (!cameraVideo || !cameraCanvas) {
          return;
        }

        if (selectedFiles.length >= maxUploads) {
          setStatus(`Upload queue is full (${maxUploads}/${maxUploads}).`, "error");
          closeCameraModal();
          return;
        }

        const width = cameraVideo.videoWidth;
        const height = cameraVideo.videoHeight;
        if (!width || !height) {
          setStatus("Camera is still warming up. Try again in a moment.", "error");
          return;
        }

        cameraCanvas.width = width;
        cameraCanvas.height = height;
        const context = cameraCanvas.getContext("2d");
        if (!context) {
          setStatus("Failed to capture image from camera.", "error");
          return;
        }

        context.drawImage(cameraVideo, 0, 0, width, height);
        cameraCanvas.toBlob(
          (blob) => {
            if (!blob) {
              setStatus("Failed to capture image from camera.", "error");
              return;
            }

            const timestamp = new Date().toISOString().replace(/[.:]/g, "-");
            const capturedFile = new File([blob], `live_${timestamp}.jpg`, { type: "image/jpeg" });
            addFilesToQueue([capturedFile], "live camera");

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
      }

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
          if (selectedFiles.length === 0) {
            setStatus("Upload at least one image before registering.", "error");
            return;
          }

          registerButton.disabled = true;
          setStatus("Registering profile...", "neutral");

          try {
            const branch = inferBranchFromBatch(batch);
            const response = await registerAdminStudent({
              student_id: studentId,
              name: studentName,
              branch,
              batch,
              images: selectedFiles
            });

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
            updateUploadQueue();
          } catch (apiError) {
            setStatus(apiError.message || "Registration failed.", "error");
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
      };
    },
    [onLogout]
  );

  return (
    <div className="relative h-screen w-full bg-white">
      <StitchIframe html={html} title="Admin Biometrics Registration" onBind={bindActions} />
    </div>
  );
}
