import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The UI talks only to the local FastAPI backend; /api is proxied in development.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3300,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8300" },
  },
});
