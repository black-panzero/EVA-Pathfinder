import { useEffect, useRef } from "react";
import { BookOpen, GitCompareArrows, ShieldCheck, SlidersHorizontal, TriangleAlert, X } from "lucide-react";

const ITEMS = [
  { icon: SlidersHorizontal, t: "Plan", d: "Choose science sites in Jezero Crater and set the slope, time and reserve limits" },
  { icon: GitCompareArrows, t: "Routes", d: "Compare a shortest route with one that avoids steep ground, both computed on NASA elevation data" },
  { icon: ShieldCheck, t: "Feasibility", d: "See whether the full round trip fits the budget, including the walk home" },
  { icon: TriangleAlert, t: "Contingency", d: "Block the path mid-walk and watch the planner find a way home, or say there is none" },
  { icon: BookOpen, t: "Evidence", d: "Check the source of every number: rover photos, weather records and datasets" },
];

export function Guide({ open, onClose }: { open: boolean; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const start = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) { d.showModal(); start.current?.focus(); }
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog ref={ref} className="guide" onClose={onClose} aria-labelledby="guide-h">
      <button type="button" className="icon-btn guide-x" aria-label="Close guide" onClick={onClose}><X size={18} strokeWidth={1.5} /></button>
      <p className="step-n">Operation Delta Return</p>
      <h2 id="guide-h">Plan a Mars walk that always gets the crew home</h2>
      <p className="step-d">A planner for an astronaut walk across a real 8 × 4.5 km patch of Jezero Crater, mapped from NASA orbital and rover data. Work through the five steps in order</p>
      <ol className="guide-list">
        {ITEMS.map(({ icon: Icon, t, d }, i) => (
          <li key={t}><span className="guide-n num">{i + 1}</span><Icon size={18} strokeWidth={1.5} aria-hidden="true" /><span><span className="t">{t}</span><span className="m">{d}</span></span></li>
        ))}
      </ol>
      <p className="note">Research prototype, not certified for real EVA navigation. The habitat, crew and events are simulated; terrain and observations are real. Software written with AI assistance (Claude Code); all imagery is NASA/USGS data</p>
      <div className="guide-actions"><button ref={start} type="button" className="btn primary" onClick={onClose}>Start planning</button></div>
    </dialog>
  );
}
