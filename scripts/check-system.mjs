const base = "http://127.0.0.1:8070";
const id = Date.now();

const call = async (path, options = {}) => {
  const response = await fetch(`${base}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) }
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(`${path}: ${body.detail || body.message || response.status}`);
  return body;
};

const company = await call("/auth/register-company", {
  method: "POST",
  body: JSON.stringify({ company_name: `AttendX Check ${id}`, name: "Admin", email: `check-${id}@attendx.test.com`, password: "123456" })
});
const token = company.data.token;
const headers = { Authorization: `Bearer ${token}` };
const employeeId = `EMP-${id}`;
const makeSampleImage = () => {
  const width = 32;
  const height = 32;
  const header = Buffer.from(`P6\n${width} ${height}\n255\n`, "ascii");
  const pixels = Buffer.alloc(width * height * 3);
  for (let index = 0; index < pixels.length; index += 3) {
    pixels[index] = 80 + ((index / 3) % width);
    pixels[index + 1] = 120;
    pixels[index + 2] = 170;
  }
  return `data:image/x-portable-pixmap;base64,${Buffer.concat([header, pixels]).toString("base64")}`;
};
const sampleImage = makeSampleImage();
await call("/employees/create", {
  method: "POST",
  headers,
  body: JSON.stringify({ employee_id: employeeId, name: "Test Employee", department: "Nursing", shift_type: "flexible" })
});
await call("/faces/register", {
  method: "POST",
  headers,
  body: JSON.stringify({ employee_id: employeeId, image_base64: sampleImage })
});
const scan = await call("/attendance/scan", {
  method: "POST",
  headers,
  body: JSON.stringify({ frames: [sampleImage, sampleImage, sampleImage, sampleImage, sampleImage], device_id: "automated-check" })
});
await call("/attendance/confirm", {
  method: "POST",
  headers,
  body: JSON.stringify({ employee_id: scan.data.employee_id, action: scan.data.action, device_id: "automated-check" })
});
const employees = await call("/employees/list", { headers });
const today = await call("/attendance/today", { headers });
const summary = await call("/attendance/summary", { headers });
console.log(JSON.stringify({ backend: "ok", auth: "ok", employeeCreate: "ok", faceRegister: "ok", scan: scan.data.action, attendanceConfirm: "ok", employees: employees.data.length, today: today.data.length, summary: summary.data }, null, 2));
