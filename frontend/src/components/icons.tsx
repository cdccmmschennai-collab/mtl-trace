// One icon family (lucide), one stroke weight. Icons sit next to text; they are never decorative.
import * as L from "lucide-react";
import type { LucideIcon, LucideProps } from "lucide-react";

function line(Icon: LucideIcon) {
  const Wrapped = ({ size = 16, ...props }: LucideProps) => (
    <Icon size={size} strokeWidth={1.6} aria-hidden="true" focusable="false" {...props} />
  );
  Wrapped.displayName = Icon.displayName;
  return Wrapped;
}

export const ArrowDown = line(L.ArrowDown);
export const ArrowLeft = line(L.ArrowLeft);
export const ArrowRight = line(L.ArrowRight);
export const Check = line(L.Check);
export const ChevronDown = line(L.ChevronDown);
export const ChevronUp = line(L.ChevronUp);
export const CircleAlert = line(L.CircleAlert);
export const CircleCheck = line(L.CircleCheck);
export const Combine = line(L.Combine);
export const Dot = line(L.Dot);
export const Download = line(L.Download);
export const FileSpreadsheet = line(L.FileSpreadsheet);
export const FileText = line(L.FileText);
export const GitCompareArrows = line(L.GitCompareArrows);
export const History = line(L.History);
export const ImageIcon = line(L.Image);
export const LockKeyhole = line(L.LockKeyhole);
export const Plus = line(L.Plus);
export const Search = line(L.Search);
export const ShieldCheck = line(L.ShieldCheck);
export const TriangleAlert = line(L.TriangleAlert);
export const Upload = line(L.Upload);
export const X = line(L.X);

export function Spinner({ size = 16 }: { size?: number }) {
  return <L.LoaderCircle size={size} strokeWidth={1.6} aria-hidden="true" className="spin" />;
}

/** Document icon by source type code: photo register, text documents, or spreadsheet. */
export function SourceTypeIcon({ code, size = 18 }: { code: string | null; size?: number }) {
  if (code === "ASSET") return <ImageIcon size={size} />;
  if (code === "SPIR" || code === "MTC" || code === "MOM") return <FileText size={size} />;
  return <FileSpreadsheet size={size} />;
}
