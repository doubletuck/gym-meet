import type { ReactNode } from "react";
import { Link } from "react-router";

import type { Athlete, QualificationResult, Routine } from "~/api/types";
import { countryName, flagUrl } from "~/lib/countries";
import { athleteName, formatScore } from "~/lib/format";

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
  const colors =
    result === "Q"
      ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100"
      : result === "NR"
        ? "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300"
        : "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-100";
  return (
    <abbr
      title={QUALIFICATION_LABELS[result]}
      className={`rounded px-1.5 py-0.5 text-xs font-semibold no-underline ${colors}`}
    >
      {result}
    </abbr>
  );
}

/**
 * The gymnast's name, linking to their athlete page, over their country, the
 * way a narrow results column reads best; over their club instead where the
 * entry names one (national meets, where the country is everyone's).
 */
export function Gymnast({
  athlete,
  noc,
  club,
  children,
}: {
  athlete: Athlete;
  noc: string;
  club?: string | null;
  children?: ReactNode;
}) {
  return (
    <>
      <Link
        to={`/athletes/${athlete.id}`}
        // The row expands on a tap; following the link shouldn't also toggle it
        onClick={(e) => e.stopPropagation()}
        className="font-medium hover:underline"
      >
        {athleteName(athlete)}
      </Link>
      <span className="block text-xs text-gray-500">
        <Country noc={noc} club={club} />
      </span>
      {children}
    </>
  );
}

/**
 * A country's name after its flag, where it has one; sized to the text around
 * it. Given a club, the club is named and the flag stands for the country,
 * which is named in full only when there's no flag.
 */
export function Country({ noc, club }: { noc: string; club?: string | null }) {
  const flag = flagUrl(noc);
  const country = countryName(noc);
  return (
    <>
      {flag && (
        <img
          src={flag}
          alt={club ? country : ""}
          title={club ? country : undefined}
          loading="lazy"
          className="mr-1.5 inline-block h-[0.75em] w-[1em] rounded-[1px] align-[-0.05em] ring-1 ring-black/10 dark:ring-white/15"
        />
      )}
      {club ? (flag ? club : `${club} · ${country}`) : country}
    </>
  );
}

export function statusLabel(routine: Routine): string {
  return { COMPLETED: "", DNS: "Did not start", INVALID_VAULT: "Invalid vault", UNKNOWN: "Unknown" }[routine.status];
}

/** A routine's score in a cell, with the status beside it when it isn't a completed routine (an invalid vault's 0.000). */
export function RoutineScore({ routine, score = routine.score }: { routine: Routine; score?: number | null }) {
  if (routine.status === "COMPLETED") {
    return formatScore(score);
  }
  if (score == null) {
    return <span className="font-normal text-gray-500">{statusLabel(routine)}</span>;
  }
  return (
    <>
      <span className="mr-1.5 text-xs font-normal whitespace-nowrap text-gray-500">{statusLabel(routine)}</span>
      {formatScore(score)}
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
