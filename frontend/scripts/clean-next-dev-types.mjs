import {
  existsSync,
  lstatSync,
  readdirSync,
  rmdirSync,
  unlinkSync,
} from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const devTypesDir = join(scriptDir, "..", ".next", "dev", "types");

function removeDirectoryTree(targetDir) {
  if (!existsSync(targetDir)) return;

  for (const entry of readdirSync(targetDir)) {
    const childPath = join(targetDir, entry);
    const childStat = lstatSync(childPath);
    if (childStat.isDirectory() && !childStat.isSymbolicLink()) {
      removeDirectoryTree(childPath);
    } else {
      unlinkSync(childPath);
    }
  }

  rmdirSync(targetDir);
}

// Prevent stale .next/dev/types from older Next.js versions from entering builds.
removeDirectoryTree(devTypesDir);
