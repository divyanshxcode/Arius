import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy API + SSE to the FastAPI broker so the browser stays same-origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/health": "http://localhost:8000",
      "/api": "http://localhost:8000",
      "/ai": "http://localhost:8000",
      "/exec": "http://localhost:8000",
      "/actors": "http://localhost:8000",
      "/pool": "http://localhost:8000",
      "/prices": "http://localhost:8000",
      "/history": "http://localhost:8000",
      "/events": "http://localhost:8000",
      "/hosts": "http://localhost:8000",
      "/jobs": "http://localhost:8000",
      "/orgs": "http://localhost:8000",
      "/ledger": "http://localhost:8000",
      "/results": "http://localhost:8000",
    },
  },
});
