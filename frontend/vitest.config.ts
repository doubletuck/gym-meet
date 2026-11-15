import { defineConfig } from "vitest/config";

// Separate from vite.config.ts: the React Router plugin builds the app and isn't wanted under test
export default defineConfig({
  resolve: {
    tsconfigPaths: true,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./app/test/setup.ts"],
  },
});
