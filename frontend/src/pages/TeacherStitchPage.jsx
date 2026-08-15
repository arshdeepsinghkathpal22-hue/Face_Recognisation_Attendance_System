import { useCallback, useEffect, useMemo, useState } from "react";

import StitchIframe from "@/components/StitchIframe";
import {
  getTeacherAssignments,
  processTeacherFrame,
  startTeacherSession,
  stopTeacherSession
} from "@/services/api";
import teacherLiveTemplate from "../../stitch_exports/teacher_live_attendance.html?raw";
import teacherSelectTemplate from "../../stitch_exports/teacher_select_class.html?raw";

function deriveClassType(courseName, subjectId = "") {
  const normalized = `${courseName || ""} ${subjectId || ""}`.toLowerCase();
  if (normalized.includes("lab") || normalized.includes("practical") || normalized.includes("prac")) {
    return "P";
  }
  return "L";
}

function formatTimeHHMM(date) {
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}

function plusMinutes(date, minutes) {
  return new Date(date.getTime() + minutes * 60 * 1000);
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

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function buildClassesGridMarkup(classOptions, isLoadingClasses, classLoadError, selectedClassId) {
  const headerMarkup = `
    <div class="grid grid-cols-[minmax(0,1.5fr)_minmax(0,0.7fr)_8rem] gap-3 items-center px-5 mb-3">
      <div class="text-[12px] font-semibold text-gray-700">Course Name</div>
      <div class="text-[12px] font-semibold text-gray-700">Batch</div>
      <div class="text-[12px] font-semibold text-gray-700 text-right">Action</div>
    </div>
  `;

  if (isLoadingClasses) {
    return `
      ${headerMarkup}
      <div class="bg-white rounded-lg p-6 shadow-sm border border-transparent">
        <span class="font-bold text-sm text-gray-700">Loading classes...</span>
      </div>
    `;
  }

  if (classLoadError) {
    return `
      ${headerMarkup}
      <div class="bg-white rounded-lg p-6 shadow-sm border border-red-200">
        <span class="font-bold text-sm text-red-700">${escapeHtml(classLoadError)}</span>
      </div>
    `;
  }

  if (!classOptions.length) {
    return `
      ${headerMarkup}
      <div class="bg-white rounded-lg p-6 shadow-sm border border-transparent">
        <span class="font-bold text-sm text-gray-700">No classes available.</span>
      </div>
    `;
  }

  const rowsMarkup = classOptions
    .map(
      (item) => `
        <div class="grid grid-cols-[minmax(0,1.5fr)_minmax(0,0.7fr)_8rem] gap-3 items-center bg-white rounded-lg p-5 shadow-sm border border-transparent hover:border-gray-300 transition-colors" data-class-id="${escapeHtml(item.id)}">
          <span class="font-bold text-sm">${escapeHtml(item.courseName)}</span>
          <span class="font-semibold text-sm text-gray-700">${escapeHtml(item.batch)}</span>
          <button class="${
            item.id === selectedClassId
              ? "bg-gray-700"
              : "bg-[#1a1a1a]"
          } w-full text-white text-[12px] font-bold px-5 py-2.5 rounded-md hover:bg-zinc-800 transition-colors">Select</button>
        </div>
      `
    )
    .join("");

  return `${headerMarkup}<div class="space-y-3">${rowsMarkup}</div>`;
}

export default function TeacherStitchPage({ teacher, onLogout }) {
  const [view, setView] = useState("select");
  const [classOptions, setClassOptions] = useState([]);
  const [isLoadingClasses, setIsLoadingClasses] = useState(true);
  const [classLoadError, setClassLoadError] = useState("");
  const [sessionActionError, setSessionActionError] = useState("");
  const [selectedClassId, setSelectedClassId] = useState("");
  const [activeSession, setActiveSession] = useState(null);

  useEffect(() => {
    let mounted = true;

    async function loadTeacherClasses() {
      setIsLoadingClasses(true);
      setClassLoadError("");

      try {
        const assignmentsResponse = await getTeacherAssignments();
        const nextClassOptions = (assignmentsResponse.items || []).map((assignment) => ({
          id: String(assignment.id),
          semesterId: assignment.semester_id,
          subjectId: assignment.subject_id,
          courseName: assignment.subject_name,
          batch: assignment.batch,
          displayLabel: `${assignment.subject_name} - ${assignment.batch} - ${assignment.semester_label}`,
          classType: assignment.class_type
        }));

        if (!mounted) {
          return;
        }

        setClassOptions(nextClassOptions);
        setSelectedClassId(nextClassOptions[0]?.id || "");
      } catch (apiError) {
        if (!mounted) {
          return;
        }
        setClassLoadError(apiError.message || "Failed to load assigned classes.");
        setClassOptions([]);
        setSelectedClassId("");
      } finally {
        if (mounted) {
          setIsLoadingClasses(false);
        }
      }
    }

    loadTeacherClasses();

    return () => {
      mounted = false;
    };
  }, []);

  const selectedClassOption = useMemo(
    () => classOptions.find((item) => item.id === selectedClassId) || classOptions[0] || null,
    [classOptions, selectedClassId]
  );

  const selectedClassLabel = selectedClassOption?.displayLabel || "Selected Class";

  const selectHtml = useMemo(() => {
    const classesGridMarkup = buildClassesGridMarkup(
      classOptions,
      isLoadingClasses,
      classLoadError,
      selectedClassId
    );

    let html = teacherSelectTemplate.replace(
      /Teacher: Jane Doe/g,
      `Teacher: ${escapeHtml(teacher?.name || "Teacher")}`
    );

    html = html.replace(/Teacher Dashboard:\s*Select Class/g, "Teacher Dashboard");
    html = html.replace(
      /<div class="px-16 grid grid-cols-2 gap-10">[\s\S]*?<\/div>\s*<!-- Spacer to push footer down if content is short -->/,
      `<div class="px-16">
        <section class="bg-[#f5f5f5] rounded-xl p-10" data-purpose="classes-grid-container">
          <h3 class="text-lg font-bold mb-6" style="">Classes</h3>
          ${classesGridMarkup}
        </section>
      </div>
      <!-- Spacer to push footer down if content is short -->`
    );

    return html;
  }, [teacher?.name, classOptions, isLoadingClasses, classLoadError, selectedClassId]);

  const liveHtml = useMemo(() => {
    return teacherLiveTemplate
      .replace(/Administrator/g, escapeHtml(teacher?.name || "Teacher"))
      .replace(/DAA - F5F6 - 4th Semester/g, escapeHtml(selectedClassLabel));
  }, [teacher?.name, selectedClassLabel]);

  const bindSelectActions = useCallback(
    (doc) => {
      const cleanup = [];
      const classById = new Map(classOptions.map((item) => [item.id, item]));

      const signOutAction = getSignOutAction(doc);
      if (signOutAction) {
        const handleSignOut = (event) => {
          event.preventDefault();
          void onLogout();
        };
        signOutAction.addEventListener("click", handleSignOut);
        cleanup.push(() => signOutAction.removeEventListener("click", handleSignOut));
      }

      const startSessionForOption = async (selectedOption, triggerButton) => {
        if (!selectedOption) {
          setSessionActionError("Please select a class first.");
          return;
        }

        const previousText = triggerButton?.textContent;
        if (triggerButton) {
          triggerButton.disabled = true;
          triggerButton.textContent = "Starting...";
        }

        setSessionActionError("");
        try {
          const now = new Date();
          const session = await startTeacherSession({
            batch: selectedOption.batch,
            semester_id: selectedOption.semesterId,
            subject_id: selectedOption.subjectId,
            class_type: selectedOption.classType || deriveClassType(selectedOption.courseName),
            start_time: formatTimeHHMM(now),
            end_time: formatTimeHHMM(plusMinutes(now, 50))
          });

          setSelectedClassId(selectedOption.id);
          setActiveSession({
            sessionId: session.session_id,
            classId: selectedOption.id
          });
          setView("live");
        } catch (apiError) {
          setSessionActionError(apiError.message || "Failed to start attendance session.");
        } finally {
          if (triggerButton) {
            triggerButton.disabled = false;
            if (previousText) {
              triggerButton.textContent = previousText;
            }
          }
        }
      };

      const classCards = [...doc.querySelectorAll("[data-class-id]")];
      classCards.forEach((card) => {
        const button = card.querySelector("button");
        const classId = card.getAttribute("data-class-id") || "";
        if (!button || !classId) {
          return;
        }

        const handler = (event) => {
          event.preventDefault();
          const selectedOption = classById.get(classId);
          if (!selectedOption) {
            return;
          }
          setSelectedClassId(classId);
          void startSessionForOption(selectedOption, button);
        };
        button.addEventListener("click", handler);
        cleanup.push(() => button.removeEventListener("click", handler));
      });

      const nextButton = [...doc.querySelectorAll("button")].find((button) =>
        button.textContent?.includes("Next: Record Attendance")
      );
      if (nextButton) {
        const handler = (event) => {
          event.preventDefault();
          const selectedOption = classById.get(selectedClassId) || selectedClassOption || classOptions[0] || null;
          if (selectedOption) {
            setSelectedClassId(selectedOption.id);
          }
          void startSessionForOption(selectedOption, nextButton);
        };
        nextButton.addEventListener("click", handler);
        cleanup.push(() => nextButton.removeEventListener("click", handler));
      }

      return () => cleanup.forEach((dispose) => dispose());
    },
    [onLogout, classOptions, selectedClassOption, selectedClassId]
  );

  const bindLiveActions = useCallback(
    (doc) => {
      const cleanup = [];
      let cameraStream = null;
      let frameIntervalId = null;
      let frameInFlight = false;
      const activeSessionId = activeSession?.sessionId;

      const logContainer = doc.querySelector('[data-purpose="attendance-log"] .attendance-log-scroll');
      const logStack = [];
      const seenDetectionKeys = new Set();

      const renderLogStack = () => {
        if (!logContainer) {
          return;
        }

        logContainer.innerHTML = "";

        if (!logStack.length) {
          const emptyState = doc.createElement("div");
          emptyState.className =
            "bg-white border border-gray-100 rounded-xl p-5 text-sm font-semibold text-gray-500 shadow-sm";
          emptyState.textContent = "No attendance marked yet.";
          logContainer.appendChild(emptyState);
          return;
        }

        logStack.forEach((entry) => {
          const isSuccess = entry.status === "registered";
          const isMismatch = entry.status === "batch_mismatch";
          const card = doc.createElement("div");
          card.className =
            isSuccess
              ? "bg-white border border-gray-100 rounded-xl p-5 flex items-center justify-between shadow-sm hover:shadow-md transition-shadow"
              : isMismatch
              ? "bg-amber-50 border border-amber-200 rounded-xl p-5 flex items-center justify-between shadow-sm hover:shadow-md transition-shadow"
              : "bg-red-50 border border-red-200 rounded-xl p-5 flex items-center justify-between shadow-sm hover:shadow-md transition-shadow";
          card.innerHTML = `
            <div>
              <p class="text-sm font-semibold text-gray-900">${escapeHtml(entry.name)}</p>
              <p class="text-xs text-gray-500">${escapeHtml(entry.studentId)}</p>
              ${
                entry.warning
                  ? `<p class="text-xs ${isSuccess ? "text-gray-500" : isMismatch ? "text-amber-700" : "text-red-700"} font-semibold mt-1">${escapeHtml(entry.warning)}</p>`
                  : ""
              }
            </div>
            <div class="flex flex-col items-center">
              <div class="${isSuccess ? "bg-[#128054]" : isMismatch ? "bg-amber-500" : "bg-red-500"} rounded-full p-0.5 text-white mb-1">
                ${
                  isSuccess
                    ? '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M5 13l4 4L19 7" stroke-linecap="round" stroke-linejoin="round" stroke-width="3"></path></svg>'
                    : isMismatch
                    ? '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>'
                    : '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M6 18L18 6M6 6l12 12" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>'
                }
              </div>
              <span class="text-[9px] ${isSuccess ? "text-[#0a6640]" : isMismatch ? "text-amber-700" : "text-red-700"} font-extrabold uppercase mt-1">${isSuccess ? "Registered" : isMismatch ? "Batch mismatch" : "Not marked"}</span>
            </div>
          `;
          logContainer.appendChild(card);
        });
      };

      renderLogStack();

      const videoSection = doc.querySelector('[data-purpose="video-section"]');
      const videoContainer = videoSection?.querySelector(".aspect-video");
      const placeholderIcon = videoContainer?.querySelector("svg");

      const cameraStatus = doc.createElement("p");
      cameraStatus.className = "mt-3 text-xs font-semibold text-gray-600";
      cameraStatus.textContent = "Starting camera...";
      videoContainer?.insertAdjacentElement("afterend", cameraStatus);

      const cameraVideo = doc.createElement("video");
      cameraVideo.autoplay = true;
      cameraVideo.playsInline = true;
      cameraVideo.muted = true;
      cameraVideo.className = "absolute inset-0 h-full w-full object-cover";
      videoContainer?.insertBefore(cameraVideo, videoContainer.firstChild || null);

      const frameCanvas = doc.createElement("canvas");
      frameCanvas.className = "hidden";
      videoContainer?.appendChild(frameCanvas);

      const clearFrameLoop = () => {
        if (frameIntervalId) {
          clearInterval(frameIntervalId);
          frameIntervalId = null;
        }
      };

      const processNextFrame = async () => {
        if (!activeSessionId || frameInFlight) {
          return;
        }
        if (!cameraVideo || cameraVideo.readyState < 2) {
          return;
        }

        const width = cameraVideo.videoWidth;
        const height = cameraVideo.videoHeight;
        if (!width || !height) {
          return;
        }

        frameInFlight = true;
        try {
          let targetWidth = width;
          let targetHeight = height;
          const maxDim = 640;
          if (width > maxDim || height > maxDim) {
            if (width > height) {
              targetWidth = maxDim;
              targetHeight = Math.round((height * maxDim) / width);
            } else {
              targetHeight = maxDim;
              targetWidth = Math.round((width * maxDim) / height);
            }
          }

          frameCanvas.width = targetWidth;
          frameCanvas.height = targetHeight;
          const context = frameCanvas.getContext("2d");
          if (!context) {
            return;
          }
          context.drawImage(cameraVideo, 0, 0, targetWidth, targetHeight);

          const frameBlob = await new Promise((resolve) => {
            frameCanvas.toBlob((blob) => resolve(blob), "image/jpeg", 0.80);
          });

          if (!frameBlob) {
            return;
          }

          const frameResult = await processTeacherFrame(activeSessionId, frameBlob, 0.6, "recognize");
          const detections = frameResult.marked_in_frame || [];
          const frameDebug = frameResult.debug || null;
          if (frameDebug && doc.defaultView?.console) {
            doc.defaultView.console.debug("Attendance recognition debug", frameDebug);
          }

          const primaryDetection = detections[0] || null;
          if (primaryDetection) {
            const status = primaryDetection.status || "registered";
            const warning = primaryDetection.warning || "";

            if (status === "no_face") {
              cameraStatus.textContent = warning || "No face detected.";
              cameraStatus.className = "mt-3 text-xs font-semibold text-gray-500";
            } else if (status === "multiple_faces") {
              cameraStatus.textContent = warning || "Multiple faces detected. Please ensure only one registered student is visible.";
              cameraStatus.className = "mt-3 text-xs font-semibold text-amber-600";
            } else if (status === "face_mismatch") {
              cameraStatus.textContent = warning || "Face mismatch — student not recognized.";
              cameraStatus.className = "mt-3 text-xs font-semibold text-red-600";
            } else if (status === "subject_not_registered") {
              cameraStatus.textContent = warning || "Student is not registered for this subject.";
              cameraStatus.className = "mt-3 text-xs font-semibold text-amber-600";
            } else if (status === "batch_mismatch") {
              cameraStatus.textContent = warning || "Batch mismatch — student is not part of this class.";
              cameraStatus.className = "mt-3 text-xs font-semibold text-amber-600";
            } else if (status === "confirming") {
              cameraStatus.textContent = warning || `Face recognized — confirming...`;
              cameraStatus.className = "mt-3 text-xs font-semibold text-cyan-700";
            } else if (status === "registered" || status === "attendance_marked" || status === "already_marked") {
              const detectionKey = `${status}:${primaryDetection.student_id}`;
              if (!seenDetectionKeys.has(detectionKey)) {
                seenDetectionKeys.add(detectionKey);
                logStack.unshift({
                  studentId: primaryDetection.student_id,
                  name: primaryDetection.name || primaryDetection.student_id,
                  status: "registered",
                  warning: warning || "Attendance marked"
                });
                renderLogStack();
              }
              const registeredCount = logStack.filter((entry) => entry.status === "registered").length;
              cameraStatus.textContent = `${warning || "Attendance marked successfully."} (${registeredCount} student(s) marked)`;
              cameraStatus.className = "mt-3 text-xs font-semibold text-emerald-700";
            } else {
              cameraStatus.textContent = warning || `Status: ${status}`;
              cameraStatus.className = "mt-3 text-xs font-semibold text-gray-700";
            }
          }
        } catch (error) {
          const status = error?.status ? `HTTP ${error.status}: ` : "";
          const detail = error?.detail?.message || error?.message || "Face processing failed";
          cameraStatus.textContent = `${status}${detail}`;
          cameraStatus.className = "mt-3 text-xs font-semibold text-red-600";
          if (doc.defaultView?.console) {
            doc.defaultView.console.error("Face processing failed", error);
          }
        } finally {
          frameInFlight = false;
        }
      };

      const startFrameLoop = () => {
        clearFrameLoop();
        frameIntervalId = setInterval(() => {
          void processNextFrame();
        }, 300);
      };

      const stopCameraStream = () => {
        clearFrameLoop();
        if (cameraStream) {
          cameraStream.getTracks().forEach((track) => track.stop());
          cameraStream = null;
        }
        if (cameraVideo) {
          cameraVideo.srcObject = null;
        }
        if (placeholderIcon) {
          placeholderIcon.style.display = "";
        }
      };

      const startCameraStream = async () => {
        if (!activeSessionId) {
          cameraStatus.textContent = "Please select a class first to start attendance.";
          cameraStatus.className = "mt-3 text-xs font-semibold text-red-600";
          return;
        }

        if (!videoContainer || !doc.defaultView?.navigator?.mediaDevices?.getUserMedia) {
          cameraStatus.textContent = "Camera is not supported in this browser.";
          cameraStatus.className = "mt-3 text-xs font-semibold text-red-600";
          return;
        }

        try {
          cameraStream = await doc.defaultView.navigator.mediaDevices.getUserMedia({
            video: { facingMode: "user" },
            audio: false
          });

          cameraVideo.srcObject = cameraStream;
          await cameraVideo.play().catch(() => {});
          if (placeholderIcon) {
            placeholderIcon.style.display = "none";
          }
          cameraStatus.textContent = "Camera is live.";
          cameraStatus.className = "mt-3 text-xs font-semibold text-emerald-700";
          startFrameLoop();
        } catch (_error) {
          stopCameraStream();
          cameraStatus.textContent = "Unable to access camera. Please allow camera permission.";
          cameraStatus.className = "mt-3 text-xs font-semibold text-red-600";
        }
      };

      void startCameraStream();

      const stopButton = [...doc.querySelectorAll("button")].find((button) =>
        button.textContent?.includes("Stop & Submit Attendance")
      );
      if (stopButton) {
        const handler = async (event) => {
          event.preventDefault();
          stopCameraStream();
          if (activeSessionId) {
            try {
              await stopTeacherSession(activeSessionId);
            } catch (_error) {
              setSessionActionError("Failed to stop attendance session cleanly.");
            }
          }
          setActiveSession(null);
          setView("select");
        };
        stopButton.addEventListener("click", handler);
        cleanup.push(() => stopButton.removeEventListener("click", handler));
      }

      const signOutAction = getSignOutAction(doc);
      if (signOutAction) {
        const handleSignOut = async (event) => {
          event.preventDefault();
          stopCameraStream();
          if (activeSessionId) {
            try {
              await stopTeacherSession(activeSessionId);
            } catch (_error) {
              // Ignore stop errors during signout cleanup.
            }
          }
          setActiveSession(null);
          void onLogout();
        };
        signOutAction.addEventListener("click", handleSignOut);
        cleanup.push(() => signOutAction.removeEventListener("click", handleSignOut));
      }

      return () => {
        stopCameraStream();
        cleanup.forEach((dispose) => dispose());
        cameraVideo.remove();
        frameCanvas.remove();
        cameraStatus.remove();
      };
    },
    [onLogout, activeSession?.sessionId]
  );

  return (
    <div className="relative h-screen w-full bg-white">
      {sessionActionError ? (
        <div className="absolute top-4 left-1/2 z-20 -translate-x-1/2 rounded-md bg-red-50 px-4 py-2 text-sm font-medium text-red-700 shadow">
          {sessionActionError}
        </div>
      ) : null}
      <div className="absolute bottom-4 right-4 z-10">
        <button
          type="button"
          className="max-w-[calc(100vw-2rem)] rounded-md bg-black px-3 py-2 text-xs font-semibold leading-tight text-white shadow-lg hover:bg-gray-800"
          onClick={() => {
            if (view === "live") {
              setView("select");
              return;
            }
            if (activeSession?.sessionId) {
              setView("live");
              return;
            }
            setSessionActionError("Please press Select on a class to start live attendance.");
          }}
        >
          {view === "select" ? "Open Live Attendance" : "Back to Class Selection"}
        </button>
      </div>

      {view === "select" ? (
        <StitchIframe
          html={selectHtml}
          title="Teacher Select Class"
          onBind={bindSelectActions}
        />
      ) : (
        <StitchIframe
          html={liveHtml}
          title="Teacher Live Attendance"
          allow="camera *"
          onBind={bindLiveActions}
        />
      )}
    </div>
  );
}
