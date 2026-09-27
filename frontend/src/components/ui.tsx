import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { BRAND } from "../app/brand";
import { Check, CircleAlert, CircleCheck, Spinner, TriangleAlert } from "./icons";

// ------------------------------------------------------------------ header

export function Header({ right, brandLink }: { right?: ReactNode; brandLink?: string }) {
  const brand = (
    <>
      <img className="mt-logo" src={BRAND.logoSrc} alt={BRAND.logoAlt} />
      <span className="mt-brand-divider" aria-hidden="true" />
      <span className="mt-brand-text">
        <span className="mt-product">{BRAND.product}</span>
        <span className="mt-tagline">{BRAND.tagline}</span>
      </span>
    </>
  );
  return (
    <header className="mt-header">
      <div className="mt-header-inner">
        {brandLink ? (
          <Link to={brandLink} className="mt-brand mt-brand-link">
            {brand}
          </Link>
        ) : (
          <div className="mt-brand">{brand}</div>
        )}
        <div className="mt-spacer" />
        {right}
      </div>
    </header>
  );
}

// ------------------------------------------------------------------ status

export type Tone = "match" | "accent" | "review" | "mismatch" | "muted";

/** Icon + text status line. `busy` shows the spinner; `done` pops the check in. */
export function Status({ tone, kind, children }: { tone: Tone; kind?: "done" | "busy" | "warn" | "error"; children: ReactNode }) {
  return (
    <span className={`mt-status tone-${tone}`}>
      {kind === "done" && <CircleCheck size={15} className="pop" />}
      {kind === "busy" && <Spinner size={14} />}
      {kind === "warn" && <TriangleAlert size={15} />}
      {kind === "error" && <CircleAlert size={15} />}
      {children}
    </span>
  );
}

export type StepState = "done" | "active" | "waiting";

export function Step({
  id,
  title,
  overline,
  state,
  status,
  last,
  glowHeight = 340,
  children,
}: {
  id: string;
  title: string;
  overline?: string;
  state: StepState;
  status: ReactNode;
  last?: boolean;
  glowHeight?: number;
  children: ReactNode;
}) {
  return (
    <section id={id} className="mt-step mt-in-slow">
      <div className={`mt-step-body${last ? " is-last" : ""}`}>
        <span
          aria-hidden="true"
          className="mt-step-glow"
          style={{ height: glowHeight, opacity: state === "active" ? 1 : 0 }}
        />
        <div className="mt-step-head">
          <div className="mt-step-titles">
            <h2 className="mt-h2">{title}</h2>
            {overline && <span className="mt-overline">{overline}</span>}
          </div>
          {status}
        </div>
        {children}
      </div>
    </section>
  );
}

export function ErrorLine({ message }: { message: string | null | undefined }) {
  if (!message) return null;
  return (
    <div className="mt-error" role="alert">
      <CircleAlert size={15} />
      <span>{message}</span>
    </div>
  );
}

// ------------------------------------------------------------------ toast

export function useToast() {
  const [toast, setToast] = useState<string | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const show = useCallback((msg: string) => {
    window.clearTimeout(timer.current);
    setToast(msg);
    timer.current = window.setTimeout(() => setToast(null), 2800);
  }, []);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  return { toast, show };
}

export function Toast({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div className="mt-toast" role="status">
      <Check size={15} className="mt-toast-icon" />
      <span>{message}</span>
    </div>
  );
}

// ------------------------------------------------------------------ motion helpers

export const prefersReducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** 0 → 1 over 1.1s with ease-out cubic, once, after `delay` ms. Immediately 1 under reduced motion. */
export function useCountUp(delay = 250): number {
  const [t, setT] = useState(() => (prefersReducedMotion() ? 1 : 0));
  useEffect(() => {
    if (prefersReducedMotion()) return;
    let raf = 0;
    const t0 = performance.now() + delay;
    const step = (now: number) => {
      const k = Math.max(0, Math.min(1, (now - t0) / 1100));
      setT(1 - Math.pow(1 - k, 3));
      if (k < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [delay]);
  return t;
}

export function scrollToStep(id: string) {
  const el = document.getElementById(id);
  if (!el) return;
  const y = el.getBoundingClientRect().top + window.scrollY - 150;
  window.scrollTo({ top: Math.max(0, y), behavior: prefersReducedMotion() ? "auto" : "smooth" });
}

// ------------------------------------------------------------------ file drop zone

/** Click / keyboard / drag-and-drop target that hands selected files to `onFiles`. */
export function FileDrop({
  accept,
  multiple,
  onFiles,
  className,
  disabled,
  children,
  label,
}: {
  accept: string;
  multiple?: boolean;
  onFiles: (files: File[]) => void;
  className: string;
  disabled?: boolean;
  children: ReactNode;
  label: string;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const open = () => !disabled && input.current?.click();
  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-label={label}
      aria-disabled={disabled || undefined}
      className={`${className}${drag ? " is-drag" : ""}`}
      onClick={open}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          open();
        }
      }}
      onDragOver={(e) => {
        e.preventDefault();
        if (!drag && !disabled) setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDrag(false);
        if (disabled) return;
        const files = Array.from(e.dataTransfer.files);
        if (files.length) onFiles(multiple ? files : files.slice(0, 1));
      }}
    >
      {children}
      <input
        ref={input}
        type="file"
        accept={accept}
        multiple={multiple}
        hidden
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          e.target.value = "";
          if (files.length) onFiles(files);
        }}
      />
    </div>
  );
}
