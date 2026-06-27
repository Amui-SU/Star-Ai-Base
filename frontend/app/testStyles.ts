import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

const cssImportPattern = /^@import\s+["'](.+?\.css)["'];/gm;

export function readStylesheetWithLocalImports(
  relativePath = "app/globals.css",
) {
  const visited = new Set<string>();

  function readRecursive(path: string): string {
    const absolutePath = resolve(process.cwd(), path);
    if (visited.has(absolutePath)) return "";
    visited.add(absolutePath);

    const source = readFileSync(absolutePath, "utf8");
    return source.replace(cssImportPattern, (_match, importedPath: string) => {
      if (!importedPath.startsWith(".")) return "";
      const nestedPath = resolve(dirname(absolutePath), importedPath);
      return readRecursive(nestedPath);
    });
  }

  return readRecursive(relativePath);
}
