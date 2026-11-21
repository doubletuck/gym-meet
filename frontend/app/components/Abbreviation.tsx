import type { Apparatus } from "~/api/types";
import { APPARATUS_LABELS } from "~/lib/labels";

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
