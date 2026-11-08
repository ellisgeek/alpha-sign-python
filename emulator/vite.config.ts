import { defineConfig } from "vitest/config";

export default defineConfig({
  root: "src/page",
  build: { outDir: "../../dist", emptyOutDir: true },
  test: {
    root: ".",
    include: ["test/**/*.test.ts", "src/**/*.test.ts"],
  },
});
