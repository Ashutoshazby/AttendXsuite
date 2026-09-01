import React, { useEffect, useRef, useState } from "react";
import { Camera, LogOut, RefreshCw, ScanFace, Wifi } from "lucide-react";
import { createRoot } from "react-dom/client";

import { API_BASE, request } from "./api";
import "./styles.css";

const TOKEN = "attendxsuite_token";
const USER = "attendxsuite_user";
const DEVICE_KEY = "attendxsuite_device_id";

const readStoredUser = () => {
  try {
    return JSON.parse(localStorage.getItem(USER) || "null");
  } catch {
    localStorage.removeItem(USER);
    localStorage.removeItem(TOKEN);
    return null;
  }
};

const getDeviceId = () => {
  const existing = localStorage.getItem(DEVICE_KEY);
  if (existing) return existing;
  const next = `pwa-${crypto.randomUUID?.() || Date.now()}`;
  localStorage.setItem(DEVICE_KEY, next);
  return next;
};

function App() {
  const videoRef = useRef(null);
  const busyRef = useRef(false);
  const cooldownRef = useRef(new Map());
  const [token, setToken] = useState(localStorage.getItem(TOKEN) || "");
  const [user, setUser] = useState(readStoredUser);
  const [form, setForm] = useState({ email: "", password: "" });
  const [employees, setEmployees] = useState([]);
  const [message, setMessage] = useState("Login to start scanner.");
  const [cameraReady, setCameraReady] = useState(false);
  const [scannerOn, setScannerOn] = useState(true);
  const [last, setLast] = useState(null);
  const [candidate, setCandidate] = useState(null);
  const [deviceId] = useState(getDeviceId);

  const api = (path, options) => request(path, { token, ...options });

  const login = async (event) => {
    event.preventDefault();
    try {
      const body = await request("/auth/login", { method: "POST", body: JSON.stringify(form) });
      localStorage.setItem(TOKEN, body.data.token);
      localStorage.setItem(USER, JSON.stringify(body.data.user));
      setToken(body.data.token);
      setUser(body.data.user);
      setMessage("Starting secure camera...");
    } catch (error) {
      setMessage(error.message);
    }
  };

  const startCamera = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: { ideal: 720 } }, audio: false });
    videoRef.current.srcObject = stream;
    await videoRef.current.play();
    setCameraReady(true);
  };

  const loadEmployees = async () => {
    const response = await api("/employees/list");
    setEmployees(response.data || []);
    setMessage(`${(response.data || []).filter((item) => item.face_embeddings?.length).length}/${response.data?.length || 0} faces ready.`);
  };

  const captureFrame = () => {
    const video = videoRef.current;
    const canvas = document.createElement("canvas");
    canvas.width = 480;
    canvas.height = Math.round((video.videoHeight / video.videoWidth) * 480) || 640;
    canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", 0.78);
  };

  const scanOnce = async () => {
    if (!cameraReady || busyRef.current || !scannerOn || candidate) return;
    if (!employees.some((item) => item.face_embeddings?.length)) {
      setMessage("No registered face found. Register employee face from dashboard first.");
      return;
    }
    busyRef.current = true;
    try {
      setMessage("Scanning face...");
      const frames = [];
      for (let index = 0; index < 5; index += 1) {
        frames.push(captureFrame());
        await new Promise((resolve) => setTimeout(resolve, 160));
      }
      const response = await api("/attendance/scan", {
        method: "POST",
        body: JSON.stringify({ frames, device_id: deviceId, timestamp: new Date().toISOString() })
      });
      const match = response.data;
      const cooldownUntil = cooldownRef.current.get(match.employee_id) || 0;
      if (Date.now() < cooldownUntil) {
        setMessage(`${match.employee_name} already marked. Please wait.`);
        return;
      }
      setCandidate(match);
      setScannerOn(false);
      setMessage(`${match.employee_name} found. Confirm ${match.action}.`);
    } catch (error) {
      setMessage(error.message);
    } finally {
      busyRef.current = false;
    }
  };

  const confirmAttendance = async () => {
    if (!candidate || busyRef.current) return;
    busyRef.current = true;
    try {
      const response = await api("/attendance/confirm", {
        method: "POST",
        body: JSON.stringify({ employee_id: candidate.employee_id, action: candidate.action, device_id: deviceId, timestamp: new Date().toISOString() })
      });
      cooldownRef.current.set(candidate.employee_id, Date.now() + 90000);
      setLast({ ...candidate, type: response.data.type, time: new Date().toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata" }) });
      setCandidate(null);
      setScannerOn(true);
      setMessage(`${response.data.type} marked for ${candidate.employee_name}. Dashboard updated.`);
    } catch (error) {
      setMessage(error.message);
    } finally {
      busyRef.current = false;
    }
  };

  useEffect(() => {
    if (!token) return;
    Promise.all([loadEmployees(), startCamera()]).then(() => setMessage("Scanner ready.")).catch((error) => setMessage(error.message));
  }, [token]);

  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
  }, []);

  useEffect(() => {
    if (!token) return undefined;
    const timer = setInterval(scanOnce, 2200);
    return () => clearInterval(timer);
  }, [token, cameraReady, scannerOn, employees]);

  if (!token) {
    return (
      <main className="login">
        <form className="card" onSubmit={login}>
          <h1>AttendXsuite Kiosk</h1>
          <p>Phone PWA face attendance</p>
          <input placeholder="Email" type="email" autoComplete="off" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          <input placeholder="Password" type="password" autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          <button><Wifi size={18} /> Connect</button>
          <small>{API_BASE}</small>
          <strong>{message}</strong>
        </form>
      </main>
    );
  }

  return (
    <main className="kiosk">
      <video ref={videoRef} autoPlay muted playsInline />
      <div className="shade" />
      <header><div><span>AttendXsuite PWA</span><h1>{user?.company_name || "Kiosk"}</h1></div><button onClick={() => { localStorage.clear(); location.reload(); }}><LogOut size={18} /></button></header>
      <section className="target"><ScanFace size={86} /><p>{cameraReady ? "Camera ready" : "Starting camera"}</p></section>
      <section className="panel">
        <div className="metrics"><article><span>Scanner</span><strong>{scannerOn ? "Live" : "Paused"}</strong></article><article><span>Faces</span><strong>{employees.filter((e) => e.face_embeddings?.length).length}</strong></article></div>
        <p>{message}</p>
        {last && <div className="success"><strong>{last.employee_name}</strong><span>{last.type} at {last.time} IST</span></div>}
        {!employees.some((item) => item.face_embeddings?.length) && <div className="success warn"><strong>Face setup needed</strong><span>Open dashboard, select employee, capture face, then register face.</span></div>}
        <button onClick={scanOnce}><Camera size={20} /> Scan Now</button>
        <button className="secondary" onClick={() => setScannerOn((value) => !value)}><RefreshCw size={18} /> {scannerOn ? "Pause" : "Resume"} Live Scan</button>
      </section>
      {candidate && (
        <section className="confirm">
          <div className="confirm-card">
            {candidate.face_preview && <img src={`data:image/jpeg;base64,${candidate.face_preview}`} alt={candidate.employee_name} />}
            <h2>{candidate.employee_name} {candidate.action === "login" ? "Login" : "Logout"}</h2>
            <button onClick={confirmAttendance}>{candidate.action === "login" ? "Login" : "Logout"}</button>
            <button className="secondary" onClick={() => { setCandidate(null); setScannerOn(true); setMessage("Scanner restarted."); }}>Scan Again</button>
          </div>
        </section>
      )}
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
