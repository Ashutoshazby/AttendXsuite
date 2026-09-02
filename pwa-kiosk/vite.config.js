import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: [".loca.lt", ".trycloudflare.com"],
    proxy: {
      "/auth": "http://127.0.0.1:8070",
      "/employees": "http://127.0.0.1:8070",
      "/faces": "http://127.0.0.1:8070",
      "/attendance": "http://127.0.0.1:8070",
      "/health": "http://127.0.0.1:8070"
    },
    headers: {
      "Cache-Control": "no-store"
    }
  }
});
