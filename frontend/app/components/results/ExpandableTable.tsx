import { Fragment, useState, type ReactNode } from "react";

export type Column<T> = {
  header: string;
  /** Screen-reader name when the header is abbreviated, e.g. "Difficulty" for "D". */
  label?: string;
  cell: (row: T) => ReactNode;
  align?: "left" | "right";
  /** Shown only from the small breakpoint up; on a phone it's in the expanded row. */
  wide?: boolean;
};

/**
 * A results table whose rows expand on tap to show a detail panel. At phone
 * width the "wide" columns are hidden, so the detail panel is where their
 * values are read. Without a detail panel, rows don't expand.
 */
export function ExpandableTable<T>({
  columns,
  rows,
  rowKey,
  detail,
  caption,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  detail?: (row: T) => ReactNode;
  caption: string;
}) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
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
          {columns.map((column) => (
            <th
              key={column.header}
              scope="col"
              className={`px-2 py-2 font-medium ${column.align === "right" ? "text-right" : "text-left"} ${column.wide ? "hidden sm:table-cell" : ""}`}
            >
              {column.label ? (
                <abbr title={column.label} className="no-underline">
                  {column.header}
                </abbr>
              ) : (
                column.header
              )}
            </th>
          ))}
          {detail && (
            <th scope="col" className="w-8">
              <span className="sr-only">Details</span>
            </th>
          )}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const key = rowKey(row);
          const open = expanded.has(key);
          return (
            <Fragment key={key}>
              <tr
                onClick={detail ? () => toggle(key) : undefined}
                className={`border-b border-gray-200 dark:border-gray-800 ${detail ? "cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-900" : ""}`}
              >
                {columns.map((column) => (
                  <td
                    key={column.header}
                    className={`px-2 py-2.5 align-top ${column.align === "right" ? "text-right" : ""} ${column.wide ? "hidden sm:table-cell" : ""}`}
                  >
                    {column.cell(row)}
                  </td>
                ))}
                {detail && (
                  <td className="py-2.5 pr-1 text-right align-top">
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
                  </td>
                )}
              </tr>
              {open && detail && (
                <tr className="border-b border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-900">
                  <td colSpan={columns.length + 1} className="px-2 py-3">
                    {detail(row)}
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
