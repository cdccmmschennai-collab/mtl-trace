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
