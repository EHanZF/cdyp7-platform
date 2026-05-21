import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/cdyp7-platform/",
  server: {
    port: 5173,
    strictPort: true,
    open: true
  }
});
