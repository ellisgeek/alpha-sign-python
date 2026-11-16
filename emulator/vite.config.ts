import { defineConfig } from "vitest/config";

export default defineConfig({
  root: "src/page",
  build: { outDir: "../../dist", emptyOutDir: true },
  test: {
    root: ".",
    include: ["test/**/*.test.ts", "src/**/*.test.ts"],
    // `npm run test:coverage`: the unit tests' coverage of src/, as text and lcov
    // (coverage/lcov.info, which CI uploads to Codecov).
    coverage: {
      provider: "v8",
      include: ["src/**/*.ts"],
      exclude: ["src/**/*.test.ts", "src/core/display/manual-glyphs.ts"],
      reporter: ["text-summary", "text", "lcov"],
      reportsDirectory: "coverage",
    },
  },
});
