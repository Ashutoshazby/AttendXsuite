import React, { useEffect, useMemo, useRef, useState } from "react";
import { Activity, Camera, CheckCircle2, Clock3, LogOut, Plus, RefreshCw, Save, ShieldCheck, Trash2, UserPlus, Users } from "lucide-react";
import { createRoot } from "react-dom/client";

import { API_BASE, request } from "./api";
import "./styles.css";

const TOKEN = "attendxsuite_token";
const USER = "attendxsuite_user";

const readStoredUser = () => {
  try {
    return JSON.parse(localStorage.getItem(USER) || "null");
  } catch {
    localStorage.removeItem(USER);
    localStorage.removeItem(TOKEN);
    return null;
  }
};

function App() {
  const videoRef = useRef(null);
  const attendanceVideoRef = useRef(null);
  const [token, setToken] = useState(localStorage.getItem(TOKEN) || "");
  const [user, setUser] = useState(readStoredUser);
  const [mode, setMode] = useState("login");
  const [auth, setAuth] = useState({ company_name: "AttendXsuite", name: "Admin", email: "", password: "" });
  const [employee, setEmployee] = useState({ employee_id: "", name: "", department: "" });
  const [employees, setEmployees] = useState([]);
  const [users, setUsers] = useState([]);
  const [newUser, setNewUser] = useState({ name: "", email: "", password: "", role: "user" });
  const [attendance, setAttendance] = useState([]);
  const [summary, setSummary] = useState(null);
  const [selected, setSelected] = useState("");
  const [captured, setCaptured] = useState("");
  const [attendanceCandidate, setAttendanceCandidate] = useState(null);
  const [attendanceCameraReady, setAttendanceCameraReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("Ready.");

  const authed = Boolean(token);

  const api = (path, options) => request(path, { token, ...options });

  const refresh = async () => {
    if (!token) return;
    const requests = [
      api("/employees/list"),
      api("/attendance/today"),
      api("/attendance/summary")
    ];
    if (user?.role === "admin") requests.push(api("/auth/users"));
    const [emp, today, sum, appUsers] = await Promise.all(requests);
    setEmployees(emp.data || []);
    setAttendance(today.data || []);
    setSummary(sum.data || null);
    if (appUsers) setUsers(appUsers.data || []);
  };

  const login = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      const path = mode === "register" ? "/auth/register-company" : "/auth/login";
      const body = await request(path, { method: "POST", body: JSON.stringify(auth) });
      localStorage.setItem(TOKEN, body.data.token);
      localStorage.setItem(USER, JSON.stringify(body.data.user));
      setToken(body.data.token);
      setUser(body.data.user);
      setMessage("Signed in.");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  };

  const startCamera = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
    videoRef.current.srcObject = stream;
    await videoRef.current.play();
  };

  const startAttendanceCamera = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
    attendanceVideoRef.current.srcObject = stream;
    await attendanceVideoRef.current.play();
    setAttendanceCameraReady(true);
  };

  const captureFromVideo = (video, quality = 0.78) => {
    const canvas = document.createElement("canvas");
    canvas.width = 480;
    canvas.height = Math.round((video.videoHeight / video.videoWidth) * 480) || 360;
    canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", quality);
  };

  const capture = () => {
    setCaptured(captureFromVideo(videoRef.current, 0.8));
  };

  const createEmployee = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      await api("/employees/create", { method: "POST", body: JSON.stringify(employee) });
      setEmployee({ employee_id: "", name: "", department: "" });
      setMessage("Employee created.");
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

  const saveFace = async () => {
    setBusy(true);
    try {
      if (!selected || !captured) throw new Error("Select employee and capture a face.");
      await api("/faces/register", {
        method: "POST",
        body: JSON.stringify({
          employee_id: selected,
          image_base64: captured
        })
      });
      setCaptured("");
      setMessage("Face registered. Duplicate checks passed.");
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
      if (!employees.some((item) => item.face_embeddings?.length)) {
        throw new Error("No registered face found. Register face first.");
      }
      const frames = [];
      for (let index = 0; index < 5; index += 1) {
        frames.push(captureFromVideo(attendanceVideoRef.current));
        await new Promise((resolve) => setTimeout(resolve, 130));
      }
      const response = await api("/attendance/scan", {
        method: "POST",
        body: JSON.stringify({ frames, device_id: "dashboard-kiosk", timestamp: new Date().toISOString() })
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
  }, [token]);

  useEffect(() => {
    if (!token) return undefined;
    const source = new EventSource(`${API_BASE}/attendance/events?token=${encodeURIComponent(token)}`);
    source.addEventListener("attendance-updated", () => refresh().catch(() => {}));
    return () => source.close();
  }, [token]);

  const stats = useMemo(() => summary || { total_employees: employees.length, present_today: 0, registered_faces: 0, records_today: 0 }, [summary, employees]);

  if (!authed) {
    return (
      <main className="login">
        <form className="panel auth" onSubmit={login}>
          <h1>AttendXsuite</h1>
          <p>Hybrid hospital attendance dashboard</p>
          {mode === "register" && <input placeholder="Company name" autoComplete="off" value={auth.company_name} onChange={(e) => setAuth({ ...auth, company_name: e.target.value })} />}
          {mode === "register" && <input placeholder="Admin name" autoComplete="off" value={auth.name} onChange={(e) => setAuth({ ...auth, name: e.target.value })} />}
          <input placeholder="Email" type="email" autoComplete="off" value={auth.email} onChange={(e) => setAuth({ ...auth, email: e.target.value })} />
          <input placeholder="Password" type="password" autoComplete="new-password" value={auth.password} onChange={(e) => setAuth({ ...auth, password: e.target.value })} />
          <button disabled={busy}>{busy ? "Please wait..." : mode === "register" ? "Create Company" : "Login"}</button>
          <button type="button" className="link" onClick={() => setMode(mode === "login" ? "register" : "login")}>{mode === "login" ? "Create a company" : "Back to login"}</button>
          <strong>{message}</strong>
        </form>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand"><ShieldCheck size={26} /><div><strong>AttendXsuite</strong><span>Hospital attendance</span></div></div>
        <nav>
          <a href="#overview" className="active"><Activity size={18} /> Overview</a>
          <a href="#employees"><Users size={18} /> Employees</a>
          <a href="#users"><UserPlus size={18} /> Users</a>
          <a href="#faces"><Camera size={18} /> Face Registry</a>
          <a href="#dashboard-kiosk"><Camera size={18} /> Dashboard Kiosk</a>
          <a href="#attendance"><Clock3 size={18} /> Attendance</a>
        </nav>
      </aside>

      <section className="content">
        <header className="topbar">
          <div><span className="eyebrow">{user?.role || "admin"}</span><h1>Dashboard</h1><p>{user?.company_name}</p></div>
          <div className="row">
            <a className="button-link" href="#dashboard-kiosk"><Camera size={18} /> Mark Attendance</a>
            <button className="ghost" onClick={logout}><LogOut size={18} /> Logout</button>
          </div>
        </header>

        <section id="overview" className="hero-panel">
          <div>
            <span className="eyebrow">Live attendance control</span>
            <h2>Register faces, run kiosk scans, and track attendance in realtime.</h2>
          </div>
          <button onClick={() => refresh().catch((error) => setMessage(error.message))}><RefreshCw size={18} /> Refresh</button>
        </section>

        <section className="stats">
          <article><Users size={20} /><span>Total Employees</span><strong>{stats.total_employees ?? stats.totalEmployees}</strong></article>
          <article><Camera size={20} /><span>Registered Faces</span><strong>{stats.registered_faces ?? stats.registeredFaces}</strong></article>
          <article><Activity size={20} /><span>Present Today</span><strong>{stats.present_today ?? stats.presentToday}</strong></article>
          <article><Clock3 size={20} /><span>Records Today</span><strong>{stats.records_today ?? stats.recordsToday}</strong></article>
        </section>

        <section className="status-line">{message}</section>

        <section id="dashboard-kiosk" className="panel dashboard-kiosk">
          <div className="section-head">
            <h2><Camera size={20} /> Dashboard Attendance</h2>
            <span>{attendanceCameraReady ? "Camera ready" : "Camera off"}</span>
          </div>
          <div className="attendance-scan">
            <video ref={attendanceVideoRef} className="video" muted playsInline />
            <div className="scan-actions">
              <button type="button" onClick={startAttendanceCamera}>Start Camera</button>
              <button type="button" onClick={scanAttendance} disabled={busy}><Camera size={18} /> Scan Face</button>
            </div>
            {attendanceCandidate && (
              <div className="confirm-box">
                {attendanceCandidate.face_preview && <img src={`data:image/jpeg;base64,${attendanceCandidate.face_preview}`} alt={attendanceCandidate.employee_name} />}
                <div>
                  <h3>{attendanceCandidate.employee_name} {attendanceCandidate.action === "login" ? "Login" : "Logout"}</h3>
                  <p>Confirm this attendance action.</p>
                </div>
                <button onClick={confirmAttendance} disabled={busy}><CheckCircle2 size={18} /> {attendanceCandidate.action === "login" ? "Login" : "Logout"}</button>
                <button className="ghost" onClick={() => setAttendanceCandidate(null)}>Scan Again</button>
              </div>
            )}
          </div>
        </section>

        {user?.role !== "admin" ? (
          <section className="panel">
            <h2><Camera size={20} /> Attendance</h2>
            <p>Use the dashboard attendance scanner to mark login and logout.</p>
            <a className="button-link" href="#dashboard-kiosk">Open Attendance</a>
          </section>
        ) : (
        <>
        <section id="users" className="grid users-grid">
          <form className="panel" onSubmit={createAppUser}>
            <h2><UserPlus size={20} /> Create User</h2>
            <input placeholder="Name" autoComplete="off" value={newUser.name} onChange={(e) => setNewUser({ ...newUser, name: e.target.value })} />
            <input placeholder="Email" type="email" autoComplete="off" value={newUser.email} onChange={(e) => setNewUser({ ...newUser, email: e.target.value })} />
            <input placeholder="Password" type="password" autoComplete="new-password" value={newUser.password} onChange={(e) => setNewUser({ ...newUser, password: e.target.value })} />
            <select value={newUser.role} onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}>
              <option value="user">Normal User</option>
              <option value="admin">Admin</option>
            </select>
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
        <section className="grid admin-grid">
          <form id="employees" className="panel" onSubmit={createEmployee}>
            <h2><UserPlus size={20} /> Add Employee</h2>
            <input placeholder="Employee ID" value={employee.employee_id} onChange={(e) => setEmployee({ ...employee, employee_id: e.target.value })} />
            <input placeholder="Name" value={employee.name} onChange={(e) => setEmployee({ ...employee, name: e.target.value })} />
            <input placeholder="Department" value={employee.department} onChange={(e) => setEmployee({ ...employee, department: e.target.value })} />
            <button disabled={busy}><Plus size={18} /> Save Employee</button>
          </form>
          <section className="panel">
            <h2><Users size={20} /> Employees</h2>
            <div className="employee-list">
              {employees.map((item) => (
                <button type="button" className={`employee-row ${selected === item.employee_id ? "selected" : ""}`} key={item.employee_id} onClick={() => setSelected(item.employee_id)}>
                  <span><strong>{item.name}</strong><small>{item.employee_id} · {item.department || "No department"}</small></span>
                  <b>{item.face_embeddings?.length ? "Face Ready" : "Face Needed"}</b>
                </button>
              ))}
            </div>
          </section>
          <section id="faces" className="panel face-panel">
            <h2><Camera size={20} /> Face Registry</h2>
            <select value={selected} onChange={(e) => setSelected(e.target.value)}>
              <option value="">Select employee</option>
              {employees.map((item) => <option key={item.employee_id} value={item.employee_id}>{item.name} ({item.employee_id})</option>)}
            </select>
            <video ref={videoRef} className="video" muted playsInline />
            {captured && <img className="preview" src={captured} alt="Captured face" />}
            <div className="row">
              <button type="button" onClick={startCamera}>Start Camera</button>
              <button type="button" onClick={capture}>Capture</button>
              <button type="button" onClick={saveFace} disabled={busy}><Save size={18} /> Register Face</button>
            </div>
          </section>
        </section>
        </>
        )}
        <section id="attendance" className="panel">
          <div className="section-head">
            <h2><RefreshCw size={20} /> Attendance Today</h2>
            <span>IST timezone</span>
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Employee</th><th>Date</th><th>Check In</th><th>Check Out</th><th>Status</th></tr></thead>
              <tbody>{attendance.map((row) => {
                const loginAt = row.login || row.check_in;
                const logoutAt = row.logout || row.check_out;
                return <tr key={`${row.employee_id}-${row.date}`}><td>{row.employee_name}<small>{row.employee_id}</small></td><td>{row.date}</td><td>{loginAt ? new Date(loginAt).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata" }) : "-"}</td><td>{logoutAt ? new Date(logoutAt).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata" }) : "-"}</td><td><span className="pill">{row.status}</span></td></tr>;
              })}</tbody>
            </table>
          </div>
        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
