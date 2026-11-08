// The one page test (docs/emulator-spec.md, "Seams"): `npm run test:page`.
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "test/page",
  testMatch: "*.spec.ts",
  timeout: 30_000,
  use: { browserName: "chromium" },
});
