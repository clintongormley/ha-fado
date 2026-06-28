import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "happy-dom",
    include: ["tests/frontend/**/*.test.js"],
    setupFiles: ["tests/frontend/setup.js"],
  },
});
