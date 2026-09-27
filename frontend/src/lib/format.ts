// Display formatting only. No engineering logic lives in the frontend.

export const nf = (n: number) => n.toLocaleString("en-US");

export const fmtTime = (iso: string) =>
  new Date(iso).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });

export const fmtDay = (iso: string) =>
  new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });

/** "10:42 AM" today, "Sep 24, 2026 · 10:42 AM" on any other day. */
export function fmtWhen(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toDateString() === new Date().toDateString() ? fmtTime(iso) : `${fmtDay(iso)} · ${fmtTime(iso)}`;
}

export function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export const plural = (n: number, one: string, many = `${one}s`) => `${nf(n)} ${n === 1 ? one : many}`;

/** Latest of a set of ISO timestamps (nulls ignored). */
export function latest(...isos: (string | null | undefined)[]): string | null {
  let best: string | null = null;
  for (const t of isos) if (t && (!best || new Date(t) > new Date(best))) best = t;
  return best;
}

/**
 * Scope reference typed or derived from the file name, kept to the characters the backend accepts for a
 * milestone code (letters, digits, `.`, `_`, `-`; must start with a letter or digit; max 64).
 */
export function cleanRef(value: string): string {
  return value
    .toUpperCase()
    .replace(/\s+/g, "-")
    .replace(/[^A-Z0-9._-]/g, "")
    .replace(/-{2,}/g, "-")
    .slice(0, 64);
}

export function refFromFileName(name: string): string {
  const base = name.replace(/\.(xlsx|xlsm)$/i, "").replace(/^MTL[_-]?Scope[_-]?/i, "").replace(/_/g, "-");
  return cleanRef(base).replace(/^[^A-Z0-9]+/, "") || "NEW-SCOPE";
}

export async function sha256Hex(file: File): Promise<string | null> {
  if (!globalThis.crypto?.subtle) return null;
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}
