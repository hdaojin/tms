import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { dirname, resolve } from "node:path";

const source = resolve("node_modules/filepond/esm");
const target = resolve("static/vendor/filepond/esm");

if (!existsSync(source)) {
  console.error("FilePond is not installed. Run npm install first.");
  process.exitCode = 1;
} else {
  mkdirSync(dirname(target), { recursive: true });
  rmSync(target, { recursive: true, force: true });
  cpSync(source, target, { recursive: true });
  console.log(`Synced FilePond ESM resources to ${target}`);
}
