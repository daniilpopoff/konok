import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// В Docker бэкенд доступен как http://backend:8000, локально — http://localhost:8000
const target = process.env.VITE_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": target,
      "/media": target,
    },
  },
});
