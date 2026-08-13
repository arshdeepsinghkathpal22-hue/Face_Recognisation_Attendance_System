import { useCallback, useEffect, useMemo, useState } from "react";

import StitchIframe from "@/components/StitchIframe";
import { getAttendanceSummary, getSemesters, getStudentAttendanceHistory } from "@/services/api";
import studentDashboardTemplate from "../../stitch_exports/student_dashboard.html?raw";

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatPct(value) {
  if (value === null || value === undefined) {
    return "—";
  }
  return `${value}%`;
}

function renderMetric(metric) {
  const held = Number(metric?.held || 0);
  const attended = Number(metric?.attended || 0);
  const pct = metric?.pct;
  if (held <= 0) {
    return '<span class="text-gray-400">—</span>';
  }
  const label = `${attended}/${held} (${formatPct(pct)})`;
  if (pct !== null && pct !== undefined && pct < 75) {
    return `<span class="status-dot bg-red-500"></span><span class="text-red-600 font-bold">${label}</span>`;
  }
  return label;
}

function renderOverallMetric(metricOrValue) {
  const isObj = typeof metricOrValue === "object" && metricOrValue !== null;
  const value = isObj ? metricOrValue.pct : metricOrValue;
  const held = isObj ? Number(metricOrValue.held || 0) : null;
  const attended = isObj ? Number(metricOrValue.attended || 0) : null;
  if (value === null || value === undefined || (held !== null && held <= 0)) {
    return '<span class="text-gray-400">—</span>';
  }
  const label = held !== null ? `${attended}/${held} (${value}%)` : `${value}%`;
  if (value < 75) {
    return `<span class="text-red-600 font-bold">${label}</span>`;
  }
  return label;
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

function buildRowsMarkup(rows) {
  if (!rows.length) {
    return `
      <tr class="table-row-alt hover:bg-gray-50/30 transition-colors">
        <td class="px-8 py-6 text-sm font-semibold text-gray-800" colspan="5">No attendance data available for this semester.</td>
      </tr>
    `;
  }

  return rows
    .map(
      (row) => `
        <tr class="table-row-alt hover:bg-gray-50/30 transition-colors">
          <td class="px-8 py-6 text-sm font-semibold text-gray-800">${escapeHtml(row.subject_name)}</td>
          <td class="px-8 py-6 text-sm text-center text-gray-600 font-medium">${renderMetric(row.lecture)}</td>
          <td class="px-8 py-6 text-sm text-center text-gray-600 font-medium">${renderMetric(row.tutorial)}</td>
          <td class="px-8 py-6 text-sm text-center text-gray-600 font-medium">${renderMetric(row.practical)}</td>
          <td class="px-8 py-6 text-sm text-center font-bold text-gray-900">${renderOverallMetric(row.overall)}</td>
        </tr>
      `
    )
    .join("");
}

function updateSummaryFields(html, student) {
  let output = html;

  output = output.replace(/Alex Johnson/g, escapeHtml(student?.name || "Student"));
  output = output.replace(/ENR-2024-0891/g, escapeHtml(student?.student_id || "-"));

  output = output.replace(
    /(<span class="text-\[10px\] font-bold text-gray-400 uppercase tracking-widest">Batch<\/span>\s*<p class="text-lg font-bold text-gray-900">)([^<]*)(<\/p>)/,
    `$1${escapeHtml(student?.batch || "-")}$3`
  );

  return output;
}

function computeTotalMetrics(rows, summary) {
  const heldFromRows = rows.reduce((sum, row) => sum + Number(row.overall?.held || 0), 0);
  const attendedFromRows = rows.reduce((sum, row) => sum + Number(row.overall?.attended || 0), 0);

  const totalHeld = Number.isFinite(summary?.total_held) ? summary.total_held : heldFromRows;
  const totalAttended = Number.isFinite(summary?.total_attended) ? summary.total_attended : attendedFromRows;
  const totalPct = Number.isFinite(summary?.total_pct)
    ? summary.total_pct
    : totalHeld > 0
      ? Math.round((totalAttended / totalHeld) * 100)
      : null;

  return { totalHeld, totalAttended, totalPct };
}

function buildTotalAttendanceMarkup(rows, summary) {
  const { totalHeld, totalAttended, totalPct } = computeTotalMetrics(rows, summary);

  return `
    <section data-purpose="total-recorded-attendance" class="bg-white rounded-xl border border-gray-200 shadow-[0_1px_3px_rgba(0,0,0,0.02)] p-6" style="padding: 24px 28px; margin-bottom: 18px;">
      <div class="flex flex-col gap-2 md:flex-row md:items-center md:justify-between" style="display: flex; justify-content: space-between; gap: 16px; align-items: center; flex-wrap: wrap;">
        <p class="text-[11px] font-bold text-gray-500 uppercase tracking-widest" style="margin: 0; font-size: 11px; font-weight: 800; color: #6b7280; text-transform: uppercase;">Total Recorded Attendance</p>
        <p class="text-sm font-semibold text-gray-700" style="margin: 0; font-size: 14px; font-weight: 700; color: #374151;">
          <span class="text-gray-900">${totalAttended}</span>
          <span class="text-gray-500"> / ${totalHeld} classes attended</span>
        </p>
      </div>
      <p class="mt-2 text-2xl font-extrabold text-gray-900" style="margin: 12px 0 0; font-size: 28px; font-weight: 900; color: #111827;">${formatPct(totalPct)}</p>
    </section>
  `;
}

function buildHistoryMarkup(history) {
  if (!history || !history.length) {
    return `<div style="margin-top: 24px; padding: 20px; background: white; border-radius: 12px; color: #6b7280; font-size: 14px;">No attendance history recorded for this semester yet.</div>`;
  }
  return `
    <div style="margin-top: 24px; background: rgba(255,255,255,.96); border: 1px solid rgba(226,232,240,.9); border-radius: 12px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.02);">
      <h3 style="margin: 0 0 16px; font-size: 18px; font-weight: 800; color: #111827;">Session History Timeline</h3>
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Subject</th>
            <th>Class Type</th>
            <th>Time</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100">
          ${history
            .map(
              (item) => `
            <tr class="hover:bg-gray-50/30 transition-colors">
              <td class="px-6 py-4 text-sm font-semibold text-gray-800">${escapeHtml(item.session_date)}</td>
              <td class="px-6 py-4 text-sm text-gray-700">${escapeHtml(item.subject_name)}</td>
              <td class="px-6 py-4 text-sm text-gray-600">${escapeHtml(item.class_type === "L" ? "Lecture" : item.class_type === "P" ? "Practical" : "Tutorial")}</td>
              <td class="px-6 py-4 text-sm text-gray-500">${escapeHtml(item.start_time || "—")}</td>
              <td class="px-6 py-4 text-sm">
                ${
                  item.present === 1
                    ? '<span class="px-2.5 py-1 text-xs font-bold bg-green-100 text-green-800 rounded-md">Present</span>'
                    : '<span class="px-2.5 py-1 text-xs font-bold bg-red-100 text-red-800 rounded-md">Absent</span>'
                }
              </td>
            </tr>
          `
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function buildDashboardHtml(student, rows, summary, history) {
  let html = updateSummaryFields(studentDashboardTemplate, student);
  html = html.replace(
    /<tbody class="divide-y divide-gray-100">[\s\S]*?<\/tbody>/,
    `<tbody class="divide-y divide-gray-100">${buildRowsMarkup(rows)}</tbody>`
  );
  html = html.replace(
    '<section class="bg-white rounded-xl border border-gray-200 shadow-[0_1px_3px_rgba(0,0,0,0.02)] overflow-hidden">',
    `${buildTotalAttendanceMarkup(rows, summary)}<section class="bg-white rounded-xl border border-gray-200 shadow-[0_1px_3px_rgba(0,0,0,0.02)] overflow-hidden">`
  );
  html = html.replace(
    "</main>",
    `${buildHistoryMarkup(history)}</main>`
  );
  return html;
}

export default function StudentStitchPage({ student, onLogout }) {
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadData() {
      try {
        setError("");
        const semesters = await getSemesters();
        const firstSemester = semesters.items?.[0];
        if (!firstSemester) {
          setRows([]);
          setSummary(null);
          setHistory([]);
          return;
        }
        const [sumRes, histRes] = await Promise.all([
          getAttendanceSummary(firstSemester.id),
          getStudentAttendanceHistory(firstSemester.id).catch(() => []),
        ]);
        setRows(sumRes.rows || []);
        setSummary(sumRes);
        setHistory(histRes || []);
      } catch (apiError) {
        setError(apiError.message || "Failed to load attendance summary.");
      }
    }

    loadData();
  }, []);

  const html = useMemo(() => buildDashboardHtml(student, rows, summary, history), [student, rows, summary, history]);

  const bindActions = useCallback(
    (doc) => {
      const signOutAction = getSignOutAction(doc);
      if (!signOutAction) {
        return undefined;
      }

      const handleSignOut = (event) => {
        event.preventDefault();
        void onLogout();
      };

      signOutAction.addEventListener("click", handleSignOut);
      return () => signOutAction.removeEventListener("click", handleSignOut);
    },
    [onLogout]
  );

  return (
    <div className="relative h-screen w-full bg-white">
      {error ? (
        <div className="absolute top-4 left-1/2 z-10 -translate-x-1/2 rounded-md bg-red-50 px-4 py-2 text-sm font-medium text-red-700 shadow">
          {error}
        </div>
      ) : null}
      <StitchIframe html={html} title="Student Attendance Dashboard" onBind={bindActions} />
    </div>
  );
}

