import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ command }) => ({
  plugins: [react()],
  base: command === 'build' ? '/cdyp7-platform/' : '/',
}))
  server: {
    port: 5173
    strictPort: true
    open: true
  }

