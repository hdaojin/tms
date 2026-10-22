import {
  cpSync,
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
} from "node:fs";
import { dirname, relative, resolve } from "node:path";

const args = process.argv.slice(2);
const checkOnly = args.includes("--check");

const resources = [
  {
    name: "alpine",
    source: resolve("node_modules/@alpinejs/csp/dist/cdn.min.js"),
    target: resolve("static/js/alpinejs.min.js"),
  },
  {
    name: "mermaid",
    source: resolve("node_modules/mermaid/dist/mermaid.min.js"),
    target: resolve("static/js/mermaid.min.js"),
  },
  {
    name: "mermaid-license",
    source: resolve("node_modules/mermaid/LICENSE"),
    target: resolve("static/js/mermaid.LICENSE.txt"),
  },
  {
    name: "filepond",
    source: resolve("node_modules/filepond/esm"),
    target: resolve("static/vendor/filepond/esm"),
    directory: true,
  },
];

const missingSources = resources.filter(
  (resource) => !existsSync(resource.source),
);
if (missingSources.length > 0) {
  for (const resource of missingSources) {
    console.error(`Missing ${resource.name} source: ${resource.source}`);
  }
  console.error("Run npm ci first.");
  process.exit(1);
}

function filesMatch(source, target) {
  return (
    existsSync(target) &&
    !statSync(target).isDirectory() &&
    readFileSync(source).equals(readFileSync(target))
  );
}

function listFiles(root) {
  if (!existsSync(root) || !statSync(root).isDirectory()) return [];

  return readdirSync(root, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile())
    .map((entry) => resolve(entry.parentPath, entry.name))
    .sort();
}

function directoriesMatch(source, target) {
  const sourceFiles = listFiles(source);
  const targetFiles = listFiles(target);

  if (sourceFiles.length !== targetFiles.length) return false;

  return sourceFiles.every((sourceFile, index) => {
    const targetFile = targetFiles[index];
    return (
      relative(source, sourceFile) === relative(target, targetFile) &&
      filesMatch(sourceFile, targetFile)
    );
  });
}

if (checkOnly) {
  const staleResources = resources.filter((resource) =>
    resource.directory
      ? !directoriesMatch(resource.source, resource.target)
      : !filesMatch(resource.source, resource.target),
  );

  if (staleResources.length > 0) {
    for (const resource of staleResources) {
      console.error(`Frontend resource is stale: ${resource.name}`);
    }
    console.error("Run npm run build:frontend and commit the generated files.");
    process.exit(1);
  }

  console.log("Frontend vendor resources are up to date.");
} else {
  for (const resource of resources) {
    mkdirSync(dirname(resource.target), { recursive: true });
    if (resource.directory) {
      rmSync(resource.target, { recursive: true, force: true });
      cpSync(resource.source, resource.target, { recursive: true });
    } else {
      cpSync(resource.source, resource.target);
    }
    console.log(`Synced ${resource.name} to ${resource.target}`);
  }
}
