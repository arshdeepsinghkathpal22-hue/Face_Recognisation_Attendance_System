import { useState } from "react";

export default function LoginPage({ onStudentLogin, onTeacherLogin, onAdminLogin, error }) {
  const [mode, setMode] = useState("teacher");
  const [studentId, setStudentId] = useState("");
  const [studentPassword, setStudentPassword] = useState("");
  const [teacherId, setTeacherId] = useState("");
  const [teacherPassword, setTeacherPassword] = useState("");
  const [adminId, setAdminId] = useState("admin");
  const [adminPassword, setAdminPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      if (mode === "student") {
        await onStudentLogin(studentId.trim(), studentPassword);
      } else if (mode === "admin") {
        await onAdminLogin(adminId.trim(), adminPassword);
      } else {
        await onTeacherLogin(teacherId.trim(), teacherPassword);
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center overflow-hidden bg-[#07111f] p-4 font-display antialiased">
      <section className="relative grid w-full max-w-5xl overflow-hidden rounded-[28px] border border-white/10 bg-[#0b1627] shadow-2xl shadow-black/50 md:grid-cols-[0.95fr_1.05fr]">
        <div className="hidden flex-col justify-between border-r border-white/10 bg-[linear-gradient(145deg,#0f1f35_0%,#132b36_48%,#1d1b30_100%)] p-10 text-white md:flex">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.28em] text-cyan-200">FaceGrid</p>
            <h1 className="mt-8 text-5xl font-black leading-[0.95] tracking-tight">
              Smart attendance, clean control.
            </h1>
            <p className="mt-5 max-w-sm text-sm leading-6 text-slate-300">
              Faculty, admin, and student access in one focused workspace.
            </p>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-xl border border-white/10 bg-white/10 p-4">
              <p className="text-2xl font-black">AI</p>
              <p className="mt-1 text-[11px] font-semibold text-slate-300">Recognition</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/10 p-4">
              <p className="text-2xl font-black">Live</p>
              <p className="mt-1 text-[11px] font-semibold text-slate-300">Sessions</p>
            </div>
            <div className="rounded-xl border border-white/10 bg-white/10 p-4">
              <p className="text-2xl font-black">360</p>
              <p className="mt-1 text-[11px] font-semibold text-slate-300">Portal</p>
            </div>
          </div>
        </div>

        <div className="relative flex w-full items-center justify-center bg-[#f5f7fb] p-5 sm:p-8">
          <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-7 shadow-xl shadow-slate-950/10 sm:p-8">
          <div className="mb-7">
            <p className="text-xs font-black uppercase tracking-[0.22em] text-cyan-700">Secure Login</p>
            <h3 className="mt-2 text-3xl font-black tracking-tight text-slate-950">Welcome back</h3>
          </div>

          <div className="mb-6 grid grid-cols-3 rounded-xl border border-slate-200 bg-slate-100 p-1">
            <button
              type="button"
              className={`rounded-lg px-2 py-2.5 text-center text-xs font-black transition-all sm:text-sm ${
                mode === "teacher"
                  ? "bg-slate-950 text-white shadow-sm"
                  : "text-slate-500 hover:text-slate-950"
              }`}
              onClick={() => setMode("teacher")}
            >
              Faculty
            </button>
            <button
              type="button"
              className={`rounded-lg px-2 py-2.5 text-center text-xs font-black transition-all sm:text-sm ${
                mode === "student"
                  ? "bg-slate-950 text-white shadow-sm"
                  : "text-slate-500 hover:text-slate-950"
              }`}
              onClick={() => setMode("student")}
            >
              Student
            </button>
            <button
              type="button"
              className={`rounded-lg px-2 py-2.5 text-center text-xs font-black transition-all sm:text-sm ${
                mode === "admin"
                  ? "bg-slate-950 text-white shadow-sm"
                  : "text-slate-500 hover:text-slate-950"
              }`}
              onClick={() => setMode("admin")}
            >
              Admin
            </button>
          </div>

          <form className="space-y-5" onSubmit={handleSubmit}>
            {mode === "teacher" ? (
              <>
                <div>
                  <label className="mb-2 block text-sm font-bold text-slate-800" htmlFor="employeeId">
                    Email or Employee ID
                  </label>
                  <input
                    id="employeeId"
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-slate-950 outline-none transition-all placeholder:text-slate-400 focus:border-cyan-500 focus:bg-white focus:ring-4 focus:ring-cyan-500/15"
                    placeholder="Enter your Email or Employee ID"
                    value={teacherId}
                    onChange={(event) => setTeacherId(event.target.value)}
                    autoComplete="off"
                    required
                  />
                </div>

                <div>
                  <label className="mb-2 block text-sm font-bold text-slate-800" htmlFor="teacherPassword">
                    Password
                  </label>
                  <div className="relative">
                    <input
                      id="teacherPassword"
                      className="w-full rounded-xl border border-slate-200 bg-slate-50 py-3 pr-10 pl-4 text-slate-950 outline-none transition-all placeholder:text-slate-400 focus:border-cyan-500 focus:bg-white focus:ring-4 focus:ring-cyan-500/15"
                      placeholder="Enter your Password"
                      type={showPassword ? "text" : "password"}
                      value={teacherPassword}
                      onChange={(event) => setTeacherPassword(event.target.value)}
                      required
                    />
                    <button
                      type="button"
                      className="absolute top-1/2 right-3 -translate-y-1/2 text-slate-400 hover:text-slate-700"
                      onClick={() => setShowPassword((current) => !current)}
                    >
                      <span className="material-icons-round text-xl">
                        {showPassword ? "visibility" : "visibility_off"}
                      </span>
                    </button>
                  </div>
                </div>
              </>
            ) : mode === "admin" ? (
              <>
                <div>
                  <label className="mb-2 block text-sm font-bold text-slate-800" htmlFor="adminId">
                    Admin ID
                  </label>
                  <input
                    id="adminId"
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-slate-950 outline-none transition-all placeholder:text-slate-400 focus:border-cyan-500 focus:bg-white focus:ring-4 focus:ring-cyan-500/15"
                    placeholder="Enter your Admin ID"
                    value={adminId}
                    onChange={(event) => setAdminId(event.target.value)}
                    autoComplete="off"
                    required
                  />
                </div>

                <div>
                  <label className="mb-2 block text-sm font-bold text-slate-800" htmlFor="adminPassword">
                    Password
                  </label>
                  <div className="relative">
                    <input
                      id="adminPassword"
                      className="w-full rounded-xl border border-slate-200 bg-slate-50 py-3 pr-10 pl-4 text-slate-950 outline-none transition-all placeholder:text-slate-400 focus:border-cyan-500 focus:bg-white focus:ring-4 focus:ring-cyan-500/15"
                      placeholder="Enter your Password"
                      type={showPassword ? "text" : "password"}
                      value={adminPassword}
                      onChange={(event) => setAdminPassword(event.target.value)}
                      required
                    />
                    <button
                      type="button"
                      className="absolute top-1/2 right-3 -translate-y-1/2 text-slate-400 hover:text-slate-700"
                      onClick={() => setShowPassword((current) => !current)}
                    >
                      <span className="material-icons-round text-xl">
                        {showPassword ? "visibility" : "visibility_off"}
                      </span>
                    </button>
                  </div>
                </div>
              </>
            ) : (
              <>
                <div>
                  <label className="mb-2 block text-sm font-bold text-slate-800" htmlFor="studentId">
                    Enrollment Number
                  </label>
                  <input
                    id="studentId"
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-slate-950 outline-none transition-all placeholder:text-slate-400 focus:border-cyan-500 focus:bg-white focus:ring-4 focus:ring-cyan-500/15"
                    placeholder="Enter your Enrollment Number"
                    value={studentId}
                    onChange={(event) => setStudentId(event.target.value)}
                    autoComplete="off"
                    required
                  />
                </div>

                <div>
                  <label className="mb-2 block text-sm font-bold text-slate-800" htmlFor="studentPassword">
                    Password
                  </label>
                  <div className="relative">
                    <input
                      id="studentPassword"
                      className="w-full rounded-xl border border-slate-200 bg-slate-50 py-3 pr-10 pl-4 text-slate-950 outline-none transition-all placeholder:text-slate-400 focus:border-cyan-500 focus:bg-white focus:ring-4 focus:ring-cyan-500/15"
                      placeholder="Use your Enrollment Number"
                      type={showPassword ? "text" : "password"}
                      value={studentPassword}
                      onChange={(event) => setStudentPassword(event.target.value)}
                      required
                    />
                    <button
                      type="button"
                      className="absolute top-1/2 right-3 -translate-y-1/2 text-slate-400 hover:text-slate-700"
                      onClick={() => setShowPassword((current) => !current)}
                    >
                      <span className="material-icons-round text-xl">
                        {showPassword ? "visibility" : "visibility_off"}
                      </span>
                    </button>
                  </div>
                </div>
              </>
            )}

            <div className="flex items-center justify-between text-sm">
              <label className="group flex cursor-pointer items-center gap-2 select-none">
                <input
                  className="h-4 w-4 rounded border-slate-300 text-cyan-700 focus:ring-cyan-600"
                  type="checkbox"
                />
                <span className="text-slate-500 transition-colors group-hover:text-slate-900">
                  Remember Me
                </span>
              </label>
              <a className="font-bold text-cyan-700 transition-colors hover:text-slate-950" href="#">
                Forgot Password?
              </a>
            </div>

            {error ? <p className="text-sm font-medium text-red-600">{error}</p> : null}

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full rounded-xl bg-slate-950 py-3.5 font-black text-white shadow-lg shadow-slate-950/25 transition-all hover:bg-cyan-800 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-70"
            >
              {isSubmitting
                ? "Logging in..."
                : mode === "admin"
                  ? "Login as Admin"
                  : mode === "teacher"
                    ? "Login as Faculty"
                    : "Login as Student"}
            </button>
          </form>
          </div>
        </div>
      </section>
    </div>
  );
}
