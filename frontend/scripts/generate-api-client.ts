#!/usr/bin/env -S pnpm exec tsx
/**
 * Regenerates `src/api/schema.ts` (the typed client's type layer) from the
 * backend's OpenAPI schema using openapi-typescript.
 *
 * Usage: tsx scripts/generate-api-client.ts [path-to-openapi.json]
 *
 * The schema source defaults to `../.tmp/openapi.json`, produced by the
 * backend's `pomodoro-export-openapi` console script (see
 * `backend/pomodoro/entrypoints/export_openapi.py`) so this script never
 * needs a running server. CI regenerates this file and diffs it against the
 * committed version to catch drift (T19).
 */
import { execFile } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import openapiTS, { astToString, COMMENT_HEADER } from "openapi-typescript";

const execFileAsync = promisify(execFile);

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const FRONTEND_DIR = resolve(SCRIPT_DIR, "..");
const DEFAULT_SCHEMA_PATH = resolve(SCRIPT_DIR, "../../.tmp/openapi.json");
const OUTPUT_PATH = resolve(SCRIPT_DIR, "../src/api/schema.ts");

async function main(): Promise<void> {
  const schemaPath = process.argv[2]
    ? resolve(process.argv[2])
    : DEFAULT_SCHEMA_PATH;
  const ast = await openapiTS(new URL(`file://${schemaPath}`));
  const output = COMMENT_HEADER + astToString(ast);
  await mkdir(dirname(OUTPUT_PATH), { recursive: true });
  await writeFile(OUTPUT_PATH, output);
  // openapi-typescript's own formatting doesn't match this project's Biome
  // config (2-space indent), so reformat in place to keep `pnpm run lint`
  // green on the generated file without a lint-ignore override.
  await execFileAsync(
    "pnpm",
    ["exec", "biome", "format", "--write", OUTPUT_PATH],
    {
      cwd: FRONTEND_DIR,
    },
  );
  console.log(`Generated ${OUTPUT_PATH} from ${schemaPath}`);
}

main().catch((error: unknown) => {
  console.error(error);
  process.exitCode = 1;
});
