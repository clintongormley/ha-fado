import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";
import path from "node:path";

const repositoryRoot = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  root: path.join(repositoryRoot, "github-pages"),
  base: process.env.PAGES_BASE_PATH ?? "/",
  publicDir: path.join(repositoryRoot, "public"),
  plugins: [react()],
  build: {
    outDir: path.join(repositoryRoot, "dist-pages"),
    emptyOutDir: true,
  },
});
