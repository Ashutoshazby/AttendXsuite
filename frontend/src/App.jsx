import React, { useEffect, useMemo, useRef, useState } from "react";
import { Activity, Banknote, CalendarDays, Camera, CheckCircle2, Clock3, LogOut, Menu, Plus, RefreshCw, Save, ShieldCheck, Trash2, UserCog, UserPlus, Users, X } from "lucide-react";
import { createRoot } from "react-dom/client";

import { API_BASE, request } from "./api";
import "./styles.css";

const TOKEN = "attendxsuite_token";
const USER = "attendxsuite_user";
const MAX_FACE_SAMPLES = 5;

const blankBasicEmployee = { employee_id: "", name: "", department: "" };
const blankEmployeeDetails = {
  employee_id: "",
  name: "",
  department: "",
  phone: "",
  email: "",
  monthly_salary: "",
  overtime_hourly_rate: "",
  working_days_per_week: 6,
  standard_daily_hours: 8,
  shift_type: "flexible",
  shift_start: "",
  shift_end: "",
  active: true
};

const readStoredUser = () => {
  try {
    return JSON.parse(localStorage.getItem(USER) || "null");
  } catch {
    localStorage.removeItem(USER);
    localStorage.removeItem(TOKEN);
    return null;
  }
};

const toEmployeeForm = (employee = {}) => ({
  ...blankEmployeeDetails,
  ...employee,
  phone: employee.phone || "",
  email: employee.email || "",
  monthly_salary: employee.monthly_salary ?? employee.salary ?? "",
  overtime_hourly_rate: employee.overtime_hourly_rate ?? "",
  working_days_per_week: employee.working_days_per_week ?? 6,
  standard_daily_hours: employee.standard_daily_hours ?? 8,
  shift_start: employee.shift_start || "",
  shift_end: employee.shift_end || "",
  active: employee.active !== false
});

const cleanEmployeePayload = (form) => ({
  employee_id: form.employee_id.trim(),
  name: form.name.trim(),
  department: form.department.trim() || "General",
  phone: form.phone.trim() || null,
  email: form.email.trim() || null,
  salary: form.monthly_salary === "" ? null : Number(form.monthly_salary),
  monthly_salary: form.monthly_salary === "" ? null : Number(form.monthly_salary),
  overtime_hourly_rate: form.overtime_hourly_rate === "" ? null : Number(form.overtime_hourly_rate),
  working_days_per_week: Number(form.working_days_per_week) || 6,
  standard_daily_hours: Number(form.standard_daily_hours) || 8,
  shift_type: form.shift_type || "flexible",
  shift_start: form.shift_start || null,
  shift_end: form.shift_end || null,
  active: form.active !== false
});

const createFaceDescriptor = async (image) => {
  const face = await import("./face");
  return face.createDescriptor(image);
};

function App() {
  const faceVideoRef = useRef(null);
  const attendanceVideoRef = useRef(null);
  const [token, setToken] = useState(localStorage.getItem(TOKEN) || "");
  const [user, setUser] = useState(readStoredUser);
  const [page, setPage] = useState("overview");
  const [authMode, setAuthMode] = useState("login");
  const [auth, setAuth] = useState({ company_name: "AttendXsuite", name: "Admin", email: "", password: "" });
  const [basicEmployee, setBasicEmployee] = useState(blankBasicEmployee);
  const [employeeDetails, setEmployeeDetails] = useState(blankEmployeeDetails);
  const [employees, setEmployees] = useState([]);
  const [users, setUsers] = useState([]);
  const [newUser, setNewUser] = useState({ name: "", email: "", password: "", role: "user" });
  const [attendance, setAttendance] = useState([]);
  const [payroll, setPayroll] = useState([]);
  const [summary, setSummary] = useState(null);
  const [selected, setSelected] = useState("");
  const [faceCaptures, setFaceCaptures] = useState([]);
  const [faceDescriptors, setFaceDescriptors] = useState([]);
  const [faceSaveMode, setFaceSaveMode] = useState("append");
  const [faceCameraReady, setFaceCameraReady] = useState(false);
  const [attendanceCandidate, setAttendanceCandidate] = useState(null);
  const [attendanceCameraReady, setAttendanceCameraReady] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("Ready.");

  const authed = Boolean(token);
  const admin = user?.role === "admin";
  const availablePages = useMemo(
    () => admin
      ? [["overview", "Overview", Activity], ["face-registration", "Face Registration", Camera], ["employees", "Employees", Users], ["payroll", "Payroll", Banknote], ["users", "Users", UserPlus], ["kiosk", "Scan", Clock3], ["attendance", "Records", CalendarDays]]
      : [["kiosk", "Scan", Clock3]],
    [admin]
  );
  const selectedEmployee = useMemo(() => employees.find((item) => item.employee_id === selected), [employees, selected]);
  const stats = useMemo(() => summary || { total_employees: employees.length, present_today: 0, registered_faces: 0, records_today: 0 }, [summary, employees]);
  const api = (path, options) => request(path, { token, ...options });

  const refresh = async () => {
    if (!token) return;
    if (!admin) return;
    const requests = [api("/employees/list"), api("/attendance/today"), api("/attendance/summary")];
    if (admin) requests.push(api("/auth/users"));
    if (admin) requests.push(api("/attendance/payroll"));
    const [emp, today, sum, appUsers, payrollRows] = await Promise.all(requests);
    setEmployees(emp.data || []);
    setAttendance(today.data || []);
    setSummary(sum.data || null);
    if (appUsers) setUsers(appUsers.data || []);
    if (payrollRows) setPayroll(payrollRows.data || []);
  };

  const openPage = (nextPage) => {
    setPage(nextPage);
    setNavOpen(false);
    setMessage("Ready.");
  };

  const login = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      const path = authMode === "register" ? "/auth/register-company" : "/auth/login";
      const body = await request(path, { method: "POST", body: JSON.stringify(auth) });
      localStorage.setItem(TOKEN, body.data.token);
      localStorage.setItem(USER, JSON.stringify(body.data.user));
      setToken(body.data.token);
      setUser(body.data.user);
      setPage(body.data.user.role === "admin" ? "overview" : "kiosk");
      setMessage("Signed in.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  };

  const startFaceCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
      faceVideoRef.current.srcObject = stream;
      await faceVideoRef.current.play();
      setFaceCameraReady(true);
      setMessage("Face camera ready.");
    } catch (error) {
      setMessage(error.message || "Camera permission was blocked.");
    }
  };

  const startAttendanceCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
      attendanceVideoRef.current.srcObject = stream;
      await attendanceVideoRef.current.play();
      setAttendanceCameraReady(true);
      setMessage("Attendance camera ready.");
    } catch (error) {
      setMessage(error.message || "Camera permission was blocked.");
    }
  };

  const captureFromVideo = (video, quality = 0.78) => {
    if (!video || !video.videoWidth) throw new Error("Start camera first.");
    const canvas = document.createElement("canvas");
    canvas.width = 480;
    canvas.height = Math.round((video.videoHeight / video.videoWidth) * 480) || 360;
    canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", quality);
  };

  const createBasicEmployee = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      const payload = cleanEmployeePayload({ ...blankEmployeeDetails, ...basicEmployee });
      if (!payload.employee_id || !payload.name) throw new Error("Employee ID and name are required.");
      await api("/employees/create", { method: "POST", body: JSON.stringify(payload) });
      setSelected(payload.employee_id);
      setBasicEmployee(blankBasicEmployee);
      setMessage("Employee registered. Capture up to 5 face samples.");
      await refresh();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  };

  const captureFace = async () => {
    try {
      if (faceCaptures.length >= MAX_FACE_SAMPLES) throw new Error("Maximum 5 face samples are allowed.");
      const nextCount = faceCaptures.length + 1;
      const image = captureFromVideo(faceVideoRef.current, 0.88);
      const descriptor = await createFaceDescriptor(image);
      setFaceCaptures((items) => [...items, image]);
      setFaceDescriptors((items) => [...items, descriptor]);
      setMessage(`${nextCount}/5 face samples captured.`);
    } catch (error) {
      setMessage(error.message);
    }
  };

  const saveFaces = async () => {
    setBusy(true);
    try {
      if (!selected) throw new Error("Select an employee first.");
      if (faceCaptures.length < 3) throw new Error("Capture at least 3 face samples for reliable matching.");
      const response = await api("/faces/register", {
        method: "POST",
        body: JSON.stringify({ employee_id: selected, images_base64: faceCaptures, face_descriptors: faceDescriptors, replace_existing: faceSaveMode === "replace" })
      });
      setFaceCaptures([]);
      setFaceDescriptors([]);
      setMessage(`${response.data.registered_faces || 1} face sample(s) ${faceSaveMode === "replace" ? "updated" : "saved"}.`);
      await refresh();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  };

  const loadEmployeeDetails = (employeeId) => {
    setSelected(employeeId);
    const employee = employees.find((item) => item.employee_id === employeeId);
    setEmployeeDetails(toEmployeeForm(employee));
  };

  const saveEmployeeDetails = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      const payload = cleanEmployeePayload(employeeDetails);
      if (!payload.employee_id || !payload.name) throw new Error("Employee ID and name are required.");
      await api(`/employees/update/${encodeURIComponent(selected || payload.employee_id)}`, {
        method: "PUT",
        body: JSON.stringify(payload)
      });
      setSelected(payload.employee_id);
      setMessage("Employee details saved.");
      await refresh();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  };

  const deleteEmployee = async (employeeId) => {
    if (!employeeId) return;
    setBusy(true);
    try {
      await api(`/employees/${encodeURIComponent(employeeId)}`, { method: "DELETE" });
      if (selected === employeeId) {
        setSelected("");
        setEmployeeDetails(blankEmployeeDetails);
      }
      setMessage("Employee deleted.");
      await refresh();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  };

  const createAppUser = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      await api("/auth/users", { method: "POST", body: JSON.stringify(newUser) });
      setNewUser({ name: "", email: "", password: "", role: "user" });
      setMessage("User created.");
      await refresh();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  };

  const deleteAppUser = async (id) => {
    setBusy(true);
    try {
      await api(`/auth/users/${id}`, { method: "DELETE" });
      setMessage("User deleted.");
      await refresh();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  };

  const scanAttendance = async () => {
    setBusy(true);
    try {
      if (!attendanceCameraReady) await startAttendanceCamera();
      const frames = [];
      for (let index = 0; index < 5; index += 1) {
        frames.push(captureFromVideo(attendanceVideoRef.current));
        await new Promise((resolve) => setTimeout(resolve, 130));
      }
      const descriptors = [];
      for (const frame of frames) {
        descriptors.push(await createFaceDescriptor(frame));
      }
      const response = await api("/attendance/scan", {
        method: "POST",
        body: JSON.stringify({ frames, face_descriptors: descriptors, device_id: "dashboard-kiosk", timestamp: new Date().toISOString() })
      });
      setAttendanceCandidate(response.data);
      setMessage(`${response.data.employee_name} found. Confirm ${response.data.action}.`);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  };

  const confirmAttendance = async () => {
    if (!attendanceCandidate) return;
    setBusy(true);
    try {
      await api("/attendance/confirm", {
        method: "POST",
        body: JSON.stringify({
          employee_id: attendanceCandidate.employee_id,
          action: attendanceCandidate.action,
          device_id: "dashboard-kiosk",
          timestamp: new Date().toISOString()
        })
      });
      setMessage(`${attendanceCandidate.action} marked for ${attendanceCandidate.employee_name}.`);
      setAttendanceCandidate(null);
      await refresh();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  };

  const logout = () => {
    localStorage.clear();
    setToken("");
    setUser(null);
  };

  useEffect(() => {
    refresh().catch((error) => setMessage(error.message));
  }, [token, user?.role]);

  useEffect(() => {
    if (token && !availablePages.some(([key]) => key === page)) {
      setPage(availablePages[0][0]);
    }
  }, [token, page, availablePages]);

  useEffect(() => {
    if (!token) return undefined;
    const source = new EventSource(`${API_BASE}/attendance/events?token=${encodeURIComponent(token)}`);
    source.addEventListener("attendance-updated", () => refresh().catch(() => {}));
    return () => source.close();
  }, [token]);

  useEffect(() => {
    if (selectedEmployee) setEmployeeDetails(toEmployeeForm(selectedEmployee));
  }, [selectedEmployee?._id]);

  if (!authed) {
    return (
      <main className="login">
        <form className="panel auth" onSubmit={login}>
          <h1>AttendXsuite</h1>
          <p>Hospital attendance dashboard</p>
          {authMode === "register" && <input placeholder="Company name" autoComplete="off" value={auth.company_name} onChange={(e) => setAuth({ ...auth, company_name: e.target.value })} />}
          {authMode === "register" && <input placeholder="Admin name" autoComplete="off" value={auth.name} onChange={(e) => setAuth({ ...auth, name: e.target.value })} />}
          <input placeholder="Email" type="email" autoComplete="off" value={auth.email} onChange={(e) => setAuth({ ...auth, email: e.target.value })} />
          <input placeholder="Password" type="password" autoComplete="new-password" value={auth.password} onChange={(e) => setAuth({ ...auth, password: e.target.value })} />
          <button disabled={busy}>{busy ? "Please wait..." : authMode === "register" ? "Create Company" : "Login"}</button>
          <button type="button" className="link" onClick={() => setAuthMode(authMode === "login" ? "register" : "login")}>{authMode === "login" ? "Create a company" : "Back to login"}</button>
          <strong>{message}</strong>
        </form>
      </main>
    );
  }

  const pages = availablePages;

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand"><ShieldCheck size={26} /><div><strong>AttendXsuite</strong><span>Hospital attendance</span></div></div>
        <button type="button" className="menu-toggle" onClick={() => setNavOpen((value) => !value)} aria-label={navOpen ? "Close menu" : "Open menu"}>
          {navOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
        <nav className={navOpen ? "open" : ""}>
          {pages.map(([key, label, Icon]) => (
            <button key={key} type="button" className={page === key ? "active" : ""} onClick={() => openPage(key)}><Icon size={18} /> {label}</button>
          ))}
        </nav>
      </aside>

      <section className="content">
        <header className="topbar">
          <div><span className="eyebrow">{user?.role || "user"}</span><h1>{pages.find(([key]) => key === page)?.[1] || "Dashboard"}</h1><p>{user?.company_name}</p></div>
          <div className="row">
            <button type="button" onClick={() => refresh().catch((error) => setMessage(error.message))}><RefreshCw size={18} /> Refresh</button>
            <button className="ghost" onClick={logout}><LogOut size={18} /> Logout</button>
          </div>
        </header>

        <section className="status-line">{message}</section>

        {page === "overview" && (
          <>
            <section className="hero-panel">
              <div><span className="eyebrow">Live attendance control</span><h2>Register five face samples, manage hospital shifts, and track attendance in realtime.</h2></div>
              <div className="hero-actions">
                <button type="button" onClick={() => openPage("kiosk")}><Clock3 size={18} /> Scan Attendance</button>
                <button type="button" onClick={() => openPage("face-registration")}><Camera size={18} /> Register Face</button>
              </div>
            </section>
            <section className="stats">
              <article><Users size={20} /><span>Total Employees</span><strong>{stats.total_employees ?? stats.totalEmployees}</strong></article>
              <article><Camera size={20} /><span>Registered Faces</span><strong>{stats.registered_faces ?? stats.registeredFaces}</strong></article>
              <article><Activity size={20} /><span>Present Today</span><strong>{stats.present_today ?? stats.presentToday}</strong></article>
              <article><Clock3 size={20} /><span>Records Today</span><strong>{stats.records_today ?? stats.recordsToday}</strong></article>
            </section>
          </>
        )}

        {page === "face-registration" && admin && (
          <section className="grid face-grid">
            <form className="panel" onSubmit={createBasicEmployee}>
              <h2><UserPlus size={20} /> Basic Registration</h2>
              <input placeholder="Employee ID" value={basicEmployee.employee_id} onChange={(e) => setBasicEmployee({ ...basicEmployee, employee_id: e.target.value })} />
              <input placeholder="Name" value={basicEmployee.name} onChange={(e) => setBasicEmployee({ ...basicEmployee, name: e.target.value })} />
              <input placeholder="Department" value={basicEmployee.department} onChange={(e) => setBasicEmployee({ ...basicEmployee, department: e.target.value })} />
              <button disabled={busy}><Plus size={18} /> Create Employee</button>
            </form>

            <section className="panel">
              <div className="section-head"><h2><Camera size={20} /> Face Samples</h2><span>{faceCaptures.length}/5 captured</span></div>
              <select value={selected} onChange={(e) => loadEmployeeDetails(e.target.value)}>
                <option value="">Select employee</option>
                {employees.filter((item) => item.active !== false).map((item) => <option key={item.employee_id} value={item.employee_id}>{item.name} ({item.employee_id})</option>)}
              </select>
              <div className="segmented">
                <button type="button" className={faceSaveMode === "append" ? "active" : ""} onClick={() => setFaceSaveMode("append")}>Add Samples</button>
                <button type="button" className={faceSaveMode === "replace" ? "active" : ""} onClick={() => setFaceSaveMode("replace")}>Improve Face</button>
              </div>
              <video ref={faceVideoRef} className="video mirrored" muted playsInline />
              <div className="row">
                <button type="button" onClick={startFaceCamera}>Start Camera</button>
                <button type="button" onClick={captureFace} disabled={!faceCameraReady || faceCaptures.length >= MAX_FACE_SAMPLES}>Capture</button>
                <button type="button" onClick={saveFaces} disabled={busy || !selected || !faceCaptures.length}><Save size={18} /> {faceSaveMode === "replace" ? "Update Faces" : "Save Faces"}</button>
              </div>
              <div className="face-samples">
                {faceCaptures.map((image, index) => (
                  <button type="button" className="sample" key={`${image.length}-${index}`} onClick={() => {
                    setFaceCaptures((items) => items.filter((_, itemIndex) => itemIndex !== index));
                    setFaceDescriptors((items) => items.filter((_, itemIndex) => itemIndex !== index));
                  }}>
                    <img src={image} alt={`Face sample ${index + 1}`} />
                    <span>{index + 1}</span>
                  </button>
                ))}
              </div>
            </section>

            <section className="panel">
              <h2><Users size={20} /> Registered Employees</h2>
              <div className="employee-list">
                {employees.filter((item) => item.active !== false).map((item) => (
                  <button type="button" className={`employee-row ${selected === item.employee_id ? "selected" : ""}`} key={item.employee_id} onClick={() => loadEmployeeDetails(item.employee_id)}>
                    <span><strong>{item.name}</strong><small>{item.employee_id} | {item.department || "No department"}</small></span>
                    <b>{item.face_embeddings?.length || 0}/5 faces</b>
                  </button>
                ))}
              </div>
            </section>
          </section>
        )}

        {page === "employees" && admin && (
          <section className="grid employees-page">
            <section className="panel">
              <h2><Users size={20} /> Employees</h2>
              <div className="employee-list tall">
                {employees.filter((item) => item.active !== false).map((item) => (
                  <div className={`employee-row employee-row-actions ${selected === item.employee_id ? "selected" : ""}`} key={item.employee_id}>
                    <button type="button" className="employee-pick" onClick={() => loadEmployeeDetails(item.employee_id)}>
                      <span><strong>{item.name}</strong><small>{item.employee_id} | {item.department || "No department"}</small></span>
                      <b>Active</b>
                    </button>
                    <button type="button" className="icon-danger" disabled={busy} aria-label={`Delete ${item.name}`} onClick={() => deleteEmployee(item.employee_id)}><Trash2 size={16} /></button>
                  </div>
                ))}
              </div>
            </section>

            <form className="panel details-form" onSubmit={saveEmployeeDetails}>
              <h2><UserCog size={20} /> Employee Details</h2>
              <div className="form-grid">
                <label>Employee ID<input value={employeeDetails.employee_id} onChange={(e) => setEmployeeDetails({ ...employeeDetails, employee_id: e.target.value })} /></label>
                <label>Name<input value={employeeDetails.name} onChange={(e) => setEmployeeDetails({ ...employeeDetails, name: e.target.value })} /></label>
                <label>Department<input value={employeeDetails.department} onChange={(e) => setEmployeeDetails({ ...employeeDetails, department: e.target.value })} /></label>
                <label>Phone<input value={employeeDetails.phone} onChange={(e) => setEmployeeDetails({ ...employeeDetails, phone: e.target.value })} /></label>
                <label>Email<input type="email" value={employeeDetails.email} onChange={(e) => setEmployeeDetails({ ...employeeDetails, email: e.target.value })} /></label>
                <label>Monthly Salary<input type="number" min="0" value={employeeDetails.monthly_salary} onChange={(e) => setEmployeeDetails({ ...employeeDetails, monthly_salary: e.target.value })} /></label>
                <label>Overtime Rate / Hour<input type="number" min="0" value={employeeDetails.overtime_hourly_rate} onChange={(e) => setEmployeeDetails({ ...employeeDetails, overtime_hourly_rate: e.target.value })} /></label>
                <label>Work Days / Week<select value={employeeDetails.working_days_per_week} onChange={(e) => setEmployeeDetails({ ...employeeDetails, working_days_per_week: e.target.value })}><option value="5">5 days</option><option value="6">6 days</option><option value="7">7 days</option></select></label>
                <label>Daily Hours<input type="number" min="1" step="0.5" value={employeeDetails.standard_daily_hours} onChange={(e) => setEmployeeDetails({ ...employeeDetails, standard_daily_hours: e.target.value })} /></label>
                <label>Shift Type<select value={employeeDetails.shift_type} onChange={(e) => setEmployeeDetails({ ...employeeDetails, shift_type: e.target.value })}><option value="day">Day</option><option value="night">Night</option><option value="flexible">Flexible</option><option value="custom">Custom</option></select></label>
                <label>Shift Start<input type="time" value={employeeDetails.shift_start || ""} onChange={(e) => setEmployeeDetails({ ...employeeDetails, shift_start: e.target.value })} /></label>
                <label>Shift End<input type="time" value={employeeDetails.shift_end || ""} onChange={(e) => setEmployeeDetails({ ...employeeDetails, shift_end: e.target.value })} /></label>
              </div>
              <button disabled={busy || !employeeDetails.employee_id}><Banknote size={18} /> Save Details</button>
            </form>
          </section>
        )}

        {page === "users" && admin && (
          <section className="grid users-grid">
            <form className="panel" onSubmit={createAppUser}>
              <h2><UserPlus size={20} /> Create User</h2>
              <input placeholder="Name" autoComplete="off" value={newUser.name} onChange={(e) => setNewUser({ ...newUser, name: e.target.value })} />
              <input placeholder="Email" type="email" autoComplete="off" value={newUser.email} onChange={(e) => setNewUser({ ...newUser, email: e.target.value })} />
              <input placeholder="Password" type="password" autoComplete="new-password" value={newUser.password} onChange={(e) => setNewUser({ ...newUser, password: e.target.value })} />
              <select value={newUser.role} onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}><option value="user">Normal User</option><option value="admin">Admin</option></select>
              <button disabled={busy}><Plus size={18} /> Save User</button>
            </form>
            <section className="panel">
              <h2><ShieldCheck size={20} /> User Access</h2>
              <div className="employee-list">
                {users.map((item) => (
                  <div className="access-row" key={item.id}>
                    <span><strong>{item.name}</strong><small>{item.email}</small></span>
                    <b>{item.role}</b>
                    <button className="danger" disabled={busy || item.id === user?.id} onClick={() => deleteAppUser(item.id)}><Trash2 size={16} /> Delete</button>
                  </div>
                ))}
              </div>
            </section>
          </section>
        )}

        {page === "payroll" && admin && (
          <section className="panel">
            <div className="section-head"><h2><Banknote size={20} /> Payroll This Month</h2><span>Base salary plus overtime</span></div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Employee</th><th>Work Days</th><th>Hours</th><th>Overtime</th><th>Salary</th><th>OT Pay</th><th>Total</th></tr></thead>
                <tbody>{payroll.map((row) => (
                  <tr key={`${row.employee_id}-${row.month}`}>
                    <td>{row.employee_name}<small>{row.employee_id} | {row.department}</small></td>
                    <td>{row.worked_days}<small>{row.working_days_per_week} days/week</small></td>
                    <td>{row.worked_hours}<small>Expected {row.expected_hours}</small></td>
                    <td>{row.overtime_hours}</td>
                    <td>{row.monthly_salary}</td>
                    <td>{row.overtime_pay}</td>
                    <td><strong>{row.total_pay}</strong></td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </section>
        )}

        {page === "kiosk" && (
          <section className="panel dashboard-kiosk">
            <div className="section-head"><h2><Camera size={20} /> Attendance Scan</h2><span>{attendanceCameraReady ? "Camera ready" : "Camera off"}</span></div>
            <div className="attendance-scan">
              <video ref={attendanceVideoRef} className="video mirrored" muted playsInline />
              <div className="scan-actions">
                <button type="button" onClick={startAttendanceCamera}>Start Camera</button>
                <button type="button" onClick={scanAttendance} disabled={busy}><Camera size={18} /> Scan Face</button>
              </div>
              {attendanceCandidate && (
                <div className="confirm-box">
                  {attendanceCandidate.face_preview && <img src={`data:image/jpeg;base64,${attendanceCandidate.face_preview}`} alt={attendanceCandidate.employee_name} />}
                  <div><h3>{attendanceCandidate.employee_name} {attendanceCandidate.action === "login" ? "Login" : "Logout"}</h3><p>Confirm this attendance action{attendanceCandidate.confidence ? ` (${attendanceCandidate.confidence}% confidence)` : ""}.</p></div>
                  <button onClick={confirmAttendance} disabled={busy}><CheckCircle2 size={18} /> {attendanceCandidate.action === "login" ? "Login" : "Logout"}</button>
                  <button className="ghost" onClick={() => setAttendanceCandidate(null)}>Scan Again</button>
                </div>
              )}
            </div>
          </section>
        )}

        {page === "attendance" && (
          <section className="panel">
            <div className="section-head"><h2><RefreshCw size={20} /> Attendance Records</h2><span>Calcutta time</span></div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Employee</th><th>Date</th><th>Check In</th><th>Check Out</th><th>Status</th></tr></thead>
                <tbody>{attendance.map((row) => {
                  const loginAt = row.login || row.check_in;
                  const logoutAt = row.logout || row.check_out;
                  return <tr key={`${row.employee_id}-${row.date}`}><td>{row.employee_name}<small>{row.employee_id}</small></td><td>{row.date}</td><td>{row.login_time || (loginAt ? new Date(loginAt).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata" }) : "-")}</td><td>{row.logout_time || (logoutAt ? new Date(logoutAt).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata" }) : "-")}</td><td><span className="pill">{row.status}</span></td></tr>;
                })}</tbody>
              </table>
            </div>
          </section>
        )}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
