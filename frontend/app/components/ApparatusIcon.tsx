import type { Apparatus } from "~/api/types";

/** Line drawings on a 24-unit grid, stroked in the text colour. */
const PATHS: Record<Apparatus, string> = {
  // A square floor inside its border
  FX: "M3.5 3.5h17v17h-17ZM7 7h10v10H7Z",
  // The table top with its bent run-up end, on a neck and a solid pedestal
  VT: "M3.5 12.5 6.5 8h14M12 8v3.5M9.5 11.5h5v9h-5Z",
  // A narrow high-bar frame standing inside a wider, lower low-bar frame
  UB: "M6.5 20.5V4.5h11v16M3 20.5V12h18v8.5",
  // The beam on two legs that splay outward
  BB: "M3 8.5h18v2.5H3Zm4 2.5-2.5 8.5m12.5-8.5 2.5 8.5",
  // A body that narrows toward its base, two straight pommels, legs that splay outward
  PH: "M3 10h18l-2 4H5ZM9.75 10V7.25m4.5 2.75V7.25M7.5 14 5 20.5m11.5-6.5 2.5 6.5",
  // Two straps hanging from a frame, each with its ring
  SR: "M3.5 3h17M7.5 3v11m9-11v11M7.5 14a2.75 2.75 0 1 0 0 5.5 2.75 2.75 0 0 0 0-5.5Zm9 0a2.75 2.75 0 1 0 0 5.5 2.75 2.75 0 0 0 0-5.5Z",
  // Two bars, the far one set back and higher, each on its own uprights
  PB: "M5 6.5h16M3 9.5h16M8 6.5v12m10-12v12M6 9.5v11m10-11v11",
  // One bar on two plain uprights
  HB: "M5 20.5V4.5h14v16",
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
