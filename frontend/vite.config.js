import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the web app runs on :5173 and forwards /api to FastAPI on :8000.
// 127.0.0.1 (not "localhost") because on Windows "localhost" can resolve to the IPv6
// address ::1, while uvicorn only listens on IPv4 127.0.0.1 by default.
export default defineConfig({
  plugins: [react()],
  server: { host: true, proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: true } } },
});
