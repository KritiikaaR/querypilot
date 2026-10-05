import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, /api is proxied to the FastAPI server so no CORS setup is needed.
// Locally that's localhost:8000; in docker-compose it's the "backend" service.
// In production, set VITE_API_URL to the deployed backend URL instead.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": process.env.API_PROXY_TARGET || "http://localhost:8000" },
    // File changes from a Windows/Mac folder don't trigger events inside Docker, so poll there.
    watch: process.env.VITE_POLL === "true" ? { usePolling: true, interval: 300 } : undefined,
  },
});
