import type { AgeCategory, Apparatus, Discipline } from "~/api/types";
import { AGE_CATEGORY_LABELS, APPARATUS_LABELS, DISCIPLINE_LABELS, DISCIPLINE_OWNER } from "~/lib/labels";

/**
 * A short form with its full form as a tooltip. A spoken abbreviation is also
 * read out in full, because many screen readers ignore the tooltip and would
 * spell out a code like "PH" letter by letter.
 */
export function Abbreviation({ short, label, spoken = false }: { short: string; label: string; spoken?: boolean }) {
  return (
    <abbr title={label} className="no-underline">
      {spoken ? (
        <>
          <span aria-hidden="true">{short}</span>
          <span className="sr-only">{label}</span>
        </>
      ) : (
        short
      )}
    </abbr>
  );
}

/**
 * An apparatus by its FIG code ("PH"), read out in full; `routine` numbers a vault ("VT1"). Where both
 * disciplines are shown (a mixed team), `discipline` tells their floors apart: "M FX", "Men's Floor Exercise".
 */
export function ApparatusCode({
  apparatus,
  routine,
  discipline,
}: {
  apparatus: Apparatus;
  routine?: number;
  discipline?: Discipline;
}) {
  const suffix = routine != null ? String(routine) : "";
  return (
    <Abbreviation
      short={`${discipline ? `${discipline[0]} ` : ""}${apparatus}${suffix}`}
      label={`${discipline ? `${DISCIPLINE_OWNER[discipline]} ` : ""}${APPARATUS_LABELS[apparatus]}${suffix && ` ${suffix}`}`}
      spoken
    />
  );
}

/** A discipline by its FIG code ("WAG"), read out in full. */
export function DisciplineCode({ discipline }: { discipline: Discipline }) {
  return <Abbreviation short={discipline} label={DISCIPLINE_LABELS[discipline]} spoken />;
}

/** A discipline and age category, as results are grouped: "WAG Senior". */
export function Division({ discipline, ageCategory }: { discipline: Discipline; ageCategory: AgeCategory }) {
  return (
    <>
      <DisciplineCode discipline={discipline} /> {AGE_CATEGORY_LABELS[ageCategory]}
    </>
  );
}
