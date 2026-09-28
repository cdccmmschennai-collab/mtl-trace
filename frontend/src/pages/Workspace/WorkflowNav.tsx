import { useEffect, useState } from "react";
import { Check } from "../../components/icons";
import { scrollToStep, type StepState } from "../../components/ui";

export interface WorkflowItem {
  id: string; // the step section's element id
  label: string;
  state: StepState;
  available: boolean; // the step is rendered on the page
}

/**
 * Header segmented control: Scope · Sources · Consolidate · Compare · Excel. Clicking scrolls to the step; the
 * selection follows scrolling. Availability and completion come from workspace state — nothing is reset or fetched.
 */
export function WorkflowNav({ items }: { items: WorkflowItem[] }) {
  const [view, setView] = useState<string | null>(null);
  const ids = items.filter((i) => i.available).map((i) => i.id).join(",");

  // Scroll-spy: the last rendered step whose top is within 160px of the viewport top.
  useEffect(() => {
    const shown = ids.split(",").filter(Boolean);
    let raf = 0;
    const spy = () => {
      raf = 0;
      let cur: string | null = shown[0] ?? null;
      for (const id of shown) {
        const el = document.getElementById(id);
        if (el && el.getBoundingClientRect().top < 160) cur = id;
      }
      if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4 && shown.length > 1) {
        cur = shown[shown.length - 1];
      }
      if (window.scrollY < 40) cur = null;
      setView(cur);
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(spy);
    };
    spy();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      cancelAnimationFrame(raf);
    };
  }, [ids]);

  const fallback = [...items].reverse().find((i) => i.available && i.state === "active")?.id ?? items[0]?.id;
  const selected = items.some((i) => i.id === view && i.available) ? view : fallback;

  return (
    <div role="tablist" className="mt-seg">
      {items.map((i) => {
        const sel = i.id === selected;
        return (
          <button
            key={i.id}
            type="button"
            role="tab"
            aria-selected={sel}
            disabled={!i.available}
            className={`mt-seg-item${sel ? " is-selected" : ""}`}
            onClick={() => {
              setView(i.id);
              scrollToStep(i.id);
            }}
          >
            {i.state === "done" && i.available && <Check size={13} className="mt-seg-check" />}
            {i.label}
          </button>
        );
      })}
    </div>
  );
}
