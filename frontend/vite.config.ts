import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  define: {
    "process.env.NODE_ENV": JSON.stringify("production"),
  },
  build: {
    outDir: path.resolve(__dirname, "../src/workflow_ui/static/react-dist"),
    emptyOutDir: true,
    lib: {
      entry: path.resolve(__dirname, "src/mounts/embed.tsx"),
      name: "ReactFlowDesigner",
      formats: ["iife"],
      fileName: () => "designer.js",
    },
    rollupOptions: {
      output: {
        assetFileNames: "designer.[ext]",
        inlineDynamicImports: true,
      },
    },
    cssCodeSplit: false,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
