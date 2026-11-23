import type { AgeCategory, Apparatus, Discipline } from "~/api/types";
import { AGE_CATEGORY_LABELS, APPARATUS_LABELS, DISCIPLINE_LABELS } from "~/lib/labels";

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

/** An apparatus by its FIG code ("PH"), read out in full; `routine` numbers a vault ("VT1"). */
export function ApparatusCode({ apparatus, routine }: { apparatus: Apparatus; routine?: number }) {
  const suffix = routine != null ? String(routine) : "";
  return (
    <Abbreviation
      short={`${apparatus}${suffix}`}
      label={`${APPARATUS_LABELS[apparatus]}${suffix && ` ${suffix}`}`}
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
