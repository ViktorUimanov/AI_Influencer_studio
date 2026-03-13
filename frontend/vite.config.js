import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const repoRoot = path.resolve(__dirname, "..");
const backendDataRoot = path.resolve(__dirname, "../backend/data");

export default defineConfig({
  plugins: [react()],
  server: {
    fs: {
      allow: [repoRoot],
    },
  },
  define: {
    __BACKEND_DATA_ROOT__: JSON.stringify(backendDataRoot),
  },
});
