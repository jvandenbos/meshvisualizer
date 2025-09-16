import { NodeInfo } from '../types';

export type AliasMap = Record<string, string>;

// Convert any node ID format to hex format (!xxxxxxxx)
export function toHexId(id: string): string {
  if (!id) return id;

  // Already in hex format
  if (id.startsWith('!')) return id;

  // Convert decimal to hex
  if (/^\d+$/.test(id)) {
    return `!${parseInt(id).toString(16)}`;
  }

  // Return as-is if not recognized
  return id;
}

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

  // Check live nodes - handle both decimal and hex ID formats
  if (nodes && nodes.length) {
    // Try direct match first
    let node = nodes.find(n => n.id === id);

    // If not found and ID starts with !, try converting to decimal
    if (!node && id.startsWith('!')) {
      const hexPart = id.substring(1);
      const decimalId = parseInt(hexPart, 16).toString();
      node = nodes.find(n => n.id === decimalId);
    }

    // If not found and ID is decimal, try converting to hex
    if (!node && /^\d+$/.test(id)) {
      const hexId = `!${parseInt(id).toString(16)}`;
      node = nodes.find(n => n.id === hexId);
    }

    if (node) {
      if (node.long_name && node.long_name.trim().length > 0) return node.long_name;
      // if no long_name, try alias below, then short_name
      if (aliases) {
        const a = aliasForId(id, aliases);
        if (a) return a;
      }
      if (node.short_name && node.short_name.trim().length > 0) return node.short_name;
      // Return hex version of the ID for better display
      const hexId = toHexId(id);
      return hexId.substring(0, 9); // Show first 8 hex chars
    }
  }

  // Alias by ID patterns
  if (aliases) {
    const a = aliasForId(id, aliases);
    if (a) return a;
  }

  // Return hex version of the ID for better display
  const hexId = toHexId(id);
  if (hexId.startsWith('!')) return fallback || hexId.substring(0, 9);
  return fallback || hexId;
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

