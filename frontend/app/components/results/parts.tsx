import type { ReactNode } from "react";

import type { Athlete, QualificationResult } from "~/api/types";
import { countryName } from "~/lib/countries";
import { athleteName } from "~/lib/format";

const QUALIFICATION_LABELS: Record<QualificationResult, string> = {
  Q: "Qualified",
  R1: "First reserve",
  R2: "Second reserve",
  R3: "Third reserve",
  R4: "Fourth reserve",
  NR: "Not qualified: country already has two finalists",
};

export function QualificationBadge({ result }: { result: QualificationResult | null }) {
  if (!result) {
    return null;
  }
  const qualified = result === "Q";
  return (
    <abbr
      title={QUALIFICATION_LABELS[result]}
      className={`rounded px-1.5 py-0.5 text-xs font-semibold no-underline ${
        qualified
          ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100"
          : "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300"
      }`}
    >
      {result}
    </abbr>
  );
}

/** The gymnast's name over their country, the way a narrow results column reads best. */
export function Gymnast({ athlete, noc, children }: { athlete: Athlete; noc: string; children?: ReactNode }) {
  return (
    <>
      <span className="font-medium">{athleteName(athlete)}</span>
      <span className="block text-xs text-gray-500">{countryName(noc)}</span>
      {children}
    </>
  );
}

export function Rank({ rank }: { rank: number | null }) {
  return <span className="text-gray-500">{rank ?? "–"}</span>;
}

/** A label-value list for an expanded row. */
export function DetailList({ items }: { items: [string, string][] }) {
  const shown = items.filter(([, value]) => value !== "");
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 sm:grid-cols-[auto_1fr_auto_1fr]">
      {shown.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="text-gray-500">{label}</dt>
          <dd className="tabular-nums">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
