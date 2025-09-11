import { NodeInfo } from '../types';

export type AliasMap = Record<string, string>;

// Resolve a human-readable display name for a node ID, preferring:
// 1) Node.long_name (from live nodes)
// 2) Alias match by exact ID, or substring/endsWith of ID
// 3) Node.short_name
// 4) Fallback to provided fallback name or the raw ID
export function resolveName(
  idOrName: string,
  nodes?: NodeInfo[],
  aliases?: AliasMap,
  fallback?: string
): string {
  if (!idOrName) return fallback || 'unknown';
  const id = idOrName;

  // Check live nodes
  if (nodes && nodes.length) {
    const node = nodes.find(n => n.id === id);
    if (node) {
      if (node.long_name && node.long_name.trim().length > 0) return node.long_name;
      // if no long_name, try alias below, then short_name
      if (aliases) {
        const a = aliasForId(id, aliases);
        if (a) return a;
      }
      if (node.short_name && node.short_name.trim().length > 0) return node.short_name;
      return id;
    }
  }

  // Alias by ID patterns
  if (aliases) {
    const a = aliasForId(id, aliases);
    if (a) return a;
  }

  return fallback || id;
}

function aliasForId(id: string, aliases: AliasMap): string | null {
  // Exact match
  if (aliases[id]) return aliases[id];
  // Suffix or substring matches
  for (const key of Object.keys(aliases)) {
    if (id.endsWith(key) || id.includes(key)) return aliases[key];
  }
  return null;
}

