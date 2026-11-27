import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";

import { Abbreviation } from "../Abbreviation";

type SortDirection = "ascending" | "descending";

export type Column<T, S = never> = {
  header: string;
  /** Screen-reader name when the header is abbreviated, e.g. "Difficulty" for "D". */
  label?: string;
  /** Reads the label out in place of the header, for codes like "PH" a screen reader would spell out. */
  spoken?: boolean;
  cell: (row: T) => ReactNode;
  /** The column's cell in each of an expanded row's sub-rows; blank where absent. */
  subCell?(sub: S): ReactNode;
  align?: "left" | "right";
  /** Shown only from the small breakpoint up; on a phone it's in the expanded row. */
  wide?: boolean;
  /** Makes the column sortable by tapping its header; rows without a value sort last either way. */
  sortValue?: (row: T) => number | null | undefined;
  /** The direction of the first tap: ranks ascend, scores (the default) descend. */
  sortFirst?: SortDirection;
};

function sortRows<T, S>(rows: T[], column: Column<T, S>, direction: SortDirection): T[] {
  const value = column.sortValue!;
  const sign = direction === "ascending" ? 1 : -1;
  // Stable, so tied rows keep their published order
  return [...rows].sort((a, b) => {
    const x = value(a);
    const y = value(b);
    if (x == null || y == null) {
      return x == null ? (y == null ? 0 : 1) : -1;
    }
    return sign * (x - y);
  });
}

/**
 * A results table whose rows expand on tap to show a detail panel. At phone
 * width the "wide" columns are hidden, so their values have to be shown
 * elsewhere: in the detail panel or in another column's cell. A row whose
 * `detail` is false or null, and which has no sub-rows, doesn't expand.
 *
 * @param subRows rows an expanded row opens onto, above its detail panel, each
 *   laid out in the table's columns by their `subCell`, e.g. a team's members

 * @param defaultSort the header of the sortable column the rows arrive in
 *   order of, e.g. "#" for rows ranked as published
 * @param highlight picks out rows to mark, such as the athlete a link came
 *   from; the first is scrolled into view and its detail panel opened
 */
export function ExpandableTable<T, S = never>({
  columns,
  rows,
  rowKey,
  detail,
  subRows,
  subRowKey,
  caption,
  defaultSort,
  highlight,
}: {
  columns: Column<T, S>[];
  rows: T[];
  rowKey: (row: T) => string;
  detail?: (row: T) => ReactNode;
  subRows?: (row: T) => S[];
  subRowKey?: (sub: S) => string;
  caption: string;
  defaultSort?: string;
  highlight?: (row: T) => boolean;
}) {
  const [sort, setSort] = useState<{ header: string; direction: SortDirection } | null>(() => {
    const column = columns.find((c) => c.header === defaultSort);
    return column ? { header: column.header, direction: column.sortFirst ?? "descending" } : null;
  });
  const sortBy = (column: Column<T, S>) =>
    setSort((current) =>
      current?.header === column.header
        ? { header: column.header, direction: current.direction === "ascending" ? "descending" : "ascending" }
        : { header: column.header, direction: column.sortFirst ?? "descending" },
    );
  const sortColumn = columns.find((c) => c.header === sort?.header);
  const sorted = sortColumn?.sortValue && sort ? sortRows(rows, sortColumn, sort.direction) : rows;

  const panel = (row: T) => {
    const content = detail?.(row);
    return content == null || content === false ? null : content;
  };
  const subs = (row: T) => subRows?.(row) ?? [];
  const opens = (row: T) => panel(row) != null || subs(row).length > 0;
  const expandable = rows.some(opens);

  const highlighted = highlight ? rows.find(highlight) : undefined;
  const [expanded, setExpanded] = useState<Set<string>>(() =>
    highlighted && opens(highlighted) ? new Set([rowKey(highlighted)]) : new Set(),
  );
  const highlightedRow = useRef<HTMLTableRowElement>(null);
  const highlightedKey = highlighted ? rowKey(highlighted) : undefined;
  useEffect(() => {
    highlightedRow.current?.scrollIntoView?.({ block: "center" });
  }, [highlightedKey]);
  const toggle = (key: string) =>
    setExpanded((current) => {
      const next = new Set(current);
      if (!next.delete(key)) {
        next.add(key);
      }
      return next;
    });

  return (
    <table className="w-full border-collapse text-sm tabular-nums">
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr className="border-b border-gray-300 text-xs text-gray-500 dark:border-gray-700">
          {columns.map((column) => {
            const name = column.label ? (
              <Abbreviation short={column.header} label={column.label} spoken={column.spoken} />
            ) : (
              column.header
            );
            const direction = sort?.header === column.header ? sort.direction : undefined;
            return (
              <th
                key={column.header}
                scope="col"
                aria-sort={column.sortValue ? (direction ?? "none") : undefined}
                className={`px-2 py-2 font-medium ${column.align === "right" ? "text-right" : "text-left"} ${column.wide ? "hidden sm:table-cell" : ""}`}
              >
                {column.sortValue ? (
                  <button
                    type="button"
                    onClick={() => sortBy(column)}
                    className={`-mx-1 inline-flex items-center gap-0.5 px-1 font-medium hover:text-gray-900 dark:hover:text-gray-100 ${column.align === "right" ? "flex-row-reverse" : ""} ${direction ? "text-gray-900 dark:text-gray-100" : ""}`}
                  >
                    {name}
                    <SortArrow direction={direction} />
                  </button>
                ) : (
                  name
                )}
              </th>
            );
          })}
          {expandable && (
            <th scope="col" className="w-8">
              <span className="sr-only">Details</span>
            </th>
          )}
        </tr>
      </thead>
      <tbody>
        {sorted.map((row) => {
          const key = rowKey(row);
          const content = panel(row);
          const children = subs(row);
          const canOpen = content != null || children.length > 0;
          const open = canOpen && expanded.has(key);
          const marked = highlight?.(row) ?? false;
          return (
            <Fragment key={key}>
              <tr
                ref={key === highlightedKey ? highlightedRow : undefined}
                data-highlighted={marked || undefined}
                onClick={canOpen ? () => toggle(key) : undefined}
                className={`border-b border-gray-200 dark:border-gray-800 ${marked ? HIGHLIGHT : canOpen ? "hover:bg-gray-50 dark:hover:bg-gray-900" : ""} ${canOpen ? "cursor-pointer" : ""}`}
              >
                {columns.map((column) => (
                  <td
                    key={column.header}
                    className={`px-2 py-2.5 align-top ${column.align === "right" ? "text-right" : ""} ${column.wide ? "hidden sm:table-cell" : ""}`}
                  >
                    {column.cell(row)}
                  </td>
                ))}
                {expandable && (
                  <td className="py-2.5 pr-1 text-right align-top">
                    {canOpen && (
                      <button
                        type="button"
                        aria-expanded={open}
                        aria-label={open ? "Hide details" : "Show details"}
                        onClick={(e) => {
                          e.stopPropagation();
                          toggle(key);
                        }}
                        className="-m-2 p-2 text-gray-500"
                      >
                        <svg
                          aria-hidden
                          viewBox="0 0 20 20"
                          className={`size-5 transition-transform ${open ? "rotate-180" : ""}`}
                        >
                          <path
                            d="M5 7.5l5 5 5-5"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.75"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      </button>
                    )}
                  </td>
                )}
              </tr>
              {open &&
                children.map((sub, index) => (
                  <tr
                    key={subRowKey?.(sub) ?? index}
                    className={`border-b border-gray-100 text-gray-700 dark:border-gray-800/60 dark:text-gray-300 ${marked ? HIGHLIGHT : "bg-gray-50 dark:bg-gray-900"}`}
                  >
                    {columns.map((column) => (
                      <td
                        key={column.header}
                        className={`px-2 py-1.5 align-top ${column.align === "right" ? "text-right" : ""} ${column.wide ? "hidden sm:table-cell" : ""}`}
                      >
                        {column.subCell?.(sub)}
                      </td>
                    ))}
                    {expandable && <td />}
                  </tr>
                ))}
              {open && content != null && (
                <tr
                  className={`border-b border-gray-200 dark:border-gray-800 ${marked ? HIGHLIGHT : "bg-gray-50 dark:bg-gray-900"}`}
                >
                  <td colSpan={columns.length + 1} className="px-2 py-3">
                    {content}
                  </td>
                </tr>
              )}
            </Fragment>
          );
        })}
      </tbody>
    </table>
  );
}

// A highlighted row: tinted, with a bar down its leading edge
const HIGHLIGHT = "bg-amber-50 shadow-[inset_3px_0_0_var(--color-amber-400)] dark:bg-amber-950/40";

/** Space is kept for the arrow on unsorted columns so headers don't shift when sorted. */
function SortArrow({ direction }: { direction?: SortDirection }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 12 12"
      className={`size-3 shrink-0 ${direction ? "" : "invisible"} ${direction === "ascending" ? "rotate-180" : ""}`}
    >
      <path
        d="M6 2.5v7M3 6.5l3 3 3-3"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
