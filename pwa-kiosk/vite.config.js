import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: [".loca.lt", ".trycloudflare.com"],
    proxy: {
      "/auth": "http://127.0.0.1:8060",
      "/employees": "http://127.0.0.1:8060",
      "/faces": "http://127.0.0.1:8060",
      "/attendance": "http://127.0.0.1:8060",
      "/health": "http://127.0.0.1:8060"
    },
    headers: {
      "Cache-Control": "no-store"
    }
  }
});
