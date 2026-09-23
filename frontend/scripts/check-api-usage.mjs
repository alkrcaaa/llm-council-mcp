/**
 * Fails when a component calls an api.* method that api.js does not define.
 * A missing method only shows up at runtime ("api.saveConfig is not a function"),
 * usually inside a click handler nobody exercises before shipping.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const srcDir = process.argv[2] || join(dirname(fileURLToPath(import.meta.url)), '..', 'src');

function walk(dir) {
  return readdirSync(dir).flatMap((entry) => {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) return walk(path);
    return /\.(jsx?|mjs)$/.test(entry) ? [path] : [];
  });
}

const apiSource = readFileSync(join(srcDir, 'api.js'), 'utf8');
const defined = new Set(
  [...apiSource.matchAll(/^\s{2}(?:async\s+)?([a-zA-Z0-9_]+)\s*\(/gm)].map((m) => m[1])
);

const missing = [];
for (const file of walk(srcDir)) {
  if (file.endsWith('api.js')) continue;
  const source = readFileSync(file, 'utf8');
  for (const match of source.matchAll(/\bapi\.([a-zA-Z0-9_]+)\s*\(/g)) {
    if (!defined.has(match[1])) {
      missing.push(`${file.slice(srcDir.length + 1)}: api.${match[1]}()`);
    }
  }
}

if (missing.length > 0) {
  console.error('api methods called but not defined in api.js:');
  for (const entry of [...new Set(missing)]) console.error(`  - ${entry}`);
  process.exit(1);
}
console.log(`ok: every api.* call resolves (${defined.size} methods defined)`);
