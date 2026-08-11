import { useCallback, useEffect, useMemo, useState } from "react";

import StitchIframe from "@/components/StitchIframe";
import { getAttendanceSummary, getSemesters } from "@/services/api";
import studentDashboardTemplate from "../../stitch_exports/student_dashboard.html?raw";

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderMetric(value) {
  if (value === null || value === undefined) {
    return '<span class="text-gray-400">—</span>';
  }
  if (value < 75) {
    return `<span class="status-dot bg-red-500"></span><span class="text-red-600 font-bold">${value}%</span>`;
  }
  return `${value}%`;
}

function renderOverallMetric(value) {
  if (value === null || value === undefined) {
    return '<span class="text-gray-400">—</span>';
  }
  if (value < 75) {
    return `<span class="text-red-600">${value}%</span>`;
  }
  return `${value}%`;
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
          <td class="px-8 py-6 text-sm text-center text-gray-600 font-medium">${renderMetric(row.current_l_pct)}</td>
          <td class="px-8 py-6 text-sm text-center text-gray-400">—</td>
          <td class="px-8 py-6 text-sm text-center text-gray-600 font-medium">${renderMetric(row.current_p_pct)}</td>
          <td class="px-8 py-6 text-sm text-center font-bold text-gray-900">${renderOverallMetric(row.overall_pct)}</td>
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
  const heldFromRows = rows.reduce((sum, row) => sum + Number(row.held_l || 0) + Number(row.held_p || 0), 0);
  const attendedFromRows = rows.reduce((sum, row) => sum + Number(row.attended_l || 0) + Number(row.attended_p || 0), 0);

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
      <p class="mt-2 text-2xl font-extrabold text-gray-900" style="margin: 12px 0 0; font-size: 28px; font-weight: 900; color: #111827;">${renderOverallMetric(totalPct)}</p>
    </section>
  `;
}

function buildDashboardHtml(student, rows, summary) {
  let html = updateSummaryFields(studentDashboardTemplate, student);
  html = html.replace(
    /<tbody class="divide-y divide-gray-100">[\s\S]*?<\/tbody>/,
    `<tbody class="divide-y divide-gray-100">${buildRowsMarkup(rows)}</tbody>`
  );
  html = html.replace(
    '<section class="bg-white rounded-xl border border-gray-200 shadow-[0_1px_3px_rgba(0,0,0,0.02)] overflow-hidden">',
    `${buildTotalAttendanceMarkup(rows, summary)}<section class="bg-white rounded-xl border border-gray-200 shadow-[0_1px_3px_rgba(0,0,0,0.02)] overflow-hidden">`
  );
  return html;
}

export default function StudentStitchPage({ student, onLogout }) {
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadSummary() {
      try {
        setError("");
        const semesters = await getSemesters();
        const firstSemester = semesters.items?.[0];
        if (!firstSemester) {
          setRows([]);
          setSummary(null);
          return;
        }
        const summary = await getAttendanceSummary(firstSemester.id);
        setRows(summary.rows || []);
        setSummary(summary);
      } catch (apiError) {
        setError(apiError.message || "Failed to load attendance summary.");
      }
    }

    loadSummary();
  }, []);

  const html = useMemo(() => buildDashboardHtml(student, rows, summary), [student, rows, summary]);

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
