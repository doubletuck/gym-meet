import type { Apparatus } from "~/api/types";

/** Line drawings on a 24-unit grid, stroked in the text colour. */
const PATHS: Record<Apparatus, string> = {
  // A floor square seen at an angle
  FX: "M2.5 17.5 7.5 7h14l-5 10.5Z",
  // The table's padded top on a column and splayed feet
  VT: "M5.5 6.5h13a1.75 1.75 0 0 1 0 3.5h-13a1.75 1.75 0 0 1 0-3.5ZM12 10v7m-4 3.5 4-3.5 4 3.5",
  // A low bar and a high bar, each on its two uprights
  UB: "M2.5 14.5h9m-8 0v6.5m7-6.5v6.5M12.5 4.5h9m-8 0v16.5m7-16.5v16.5",
  // The beam on two legs
  BB: "M3 8.5h18v2.5H3Zm3.5 2.5v8.5m11-8.5v8.5m-13 0h4m7 0h4",
  // The horse's body, its two pommels, and legs
  PH: "M5 11h14a2 2 0 0 1 0 4H5a2 2 0 0 1 0-4Zm3.5 0V9.5a1.25 1.25 0 0 1 2.5 0V11m2 0V9.5a1.25 1.25 0 0 1 2.5 0V11M6.5 15v5.5m11-5.5v5.5",
  // Two straps hanging from a frame, each with its ring
  SR: "M3.5 3h17M7.5 3v11m9-11v11M7.5 14a2.75 2.75 0 1 0 0 5.5 2.75 2.75 0 0 0 0-5.5Zm9 0a2.75 2.75 0 1 0 0 5.5 2.75 2.75 0 0 0 0-5.5Z",
  // Two bars side by side at one height, on two uprights
  PB: "M3 8h18M3 11h18M6.5 11v9.5m11-9.5v9.5M6.5 8v3m11-3v3",
  // One bar on tall uprights, held by cables
  HB: "M3 4.5h18M6 4.5v16m12-16v16M6 4.5l-3.5 16m15.5-16 3.5 16",
};

/**
 * A small drawing of an apparatus, to set beside its code. Decorative: the
 * code says which apparatus it is, so screen readers skip the drawing.
 */
export function ApparatusIcon({ apparatus, className = "size-5" }: { apparatus: Apparatus; className?: string }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`shrink-0 ${className}`}
    >
      <path d={PATHS[apparatus]} />
    </svg>
  );
}
