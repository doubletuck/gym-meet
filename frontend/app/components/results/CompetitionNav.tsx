import { Link } from "react-router";

import type { AgeCategory, Discipline, EventDetail } from "~/api/types";
import { ApparatusCode, Division } from "~/components/Abbreviation";
import { competitionTabs, memberFor, tabOf, type CompetitionTab, type TabMember } from "~/lib/competitionTabs";
import { formatCompetitionDate } from "~/lib/format";
import { divisionPath } from "~/lib/labels";

type Where = {
  event: EventDetail;
  discipline: Discipline;
  ageCategory: AgeCategory;
  /** The competition (or ranking) shown */
  slug: string;
  /** The results view shown (`?view=`), kept where the next competition has it */
  view: string | null;
  /** The athlete whose rows are highlighted (`?athlete=`), kept within the division */
  athleteId?: number;
};

function path(
  event: EventDetail,
  discipline: Discipline,
  ageCategory: AgeCategory,
  member: TabMember,
  query: Record<string, string>,
) {
  const search = new URLSearchParams(query).toString();
  return `/events/${event.slug}/${divisionPath(discipline, ageCategory)}/${member.slug}${search && `?${search}`}`;
}

/**
 * The way around an event's results without going back: its divisions, the division's competitions
 * as tabs, and a tab's apparatus finals, rounds or parts.
 */
export function CompetitionNav({ event, discipline, ageCategory, slug, view, athleteId }: Where) {
  const tabs = competitionTabs(
    event.divisions.find((division) => division.discipline === discipline && division.ageCategory === ageCategory) ?? {
      discipline,
      ageCategory,
      rankings: [],
      competitions: [],
    },
  );
  const current = tabOf(tabs, slug);
  const query = {
    ...(view != null && { view }),
    ...(athleteId != null && { athlete: String(athleteId) }),
  };
  const to = (tab: CompetitionTab) => path(event, discipline, ageCategory, memberFor(tab, view), query);
  // An apparatus final's only view is its apparatus, so the view isn't carried between them
  const { view: _, ...withoutView } = query;

  return (
    <>
      {tabs.length > 1 && (
        <nav aria-label="Competitions" className="mt-5 overflow-x-auto border-b border-gray-200 dark:border-gray-800">
          <ul className="flex gap-1">
            {tabs.map((tab) => (
              <li key={tab.key}>
                <Link
                  to={to(tab)}
                  preventScrollReset
                  aria-current={tab === current ? "page" : undefined}
                  className={`-mb-px block whitespace-nowrap border-b-2 px-3 py-2 ${
                    tab === current
                      ? "border-blue-700 font-semibold dark:border-blue-400"
                      : "border-transparent text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
                  }`}
                >
                  {tab.label}
                  <span className="block text-xs font-normal text-gray-500">
                    {formatCompetitionDate(tab.date, tab.endDate)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      )}
      {current && current.members.length > 1 && (
        <MemberNav
          tab={current}
          slug={slug}
          to={(member) => path(event, discipline, ageCategory, member, member.apparatus ? withoutView : query)}
        />
      )}
    </>
  );
}

/**
 * A tab's apparatus, as pills like the results views (an apparatus final has no views of its own),
 * or its rounds or parts, as a segmented switch above the views.
 */
function MemberNav({ tab, slug, to }: { tab: CompetitionTab; slug: string; to: (member: TabMember) => string }) {
  const byApparatus = tab.members.every((member) => member.apparatus != null);
  return (
    <nav aria-label={byApparatus ? "Apparatus" : tab.label} className="mt-4">
      <ul
        className={
          byApparatus
            ? "flex flex-wrap gap-2"
            : "inline-flex flex-wrap gap-1 rounded-lg border border-gray-200 p-1 dark:border-gray-800"
        }
      >
        {tab.members.map((member) => {
          const active = member.slug === slug;
          return (
            <li key={member.slug}>
              <Link
                to={to(member)}
                replace
                preventScrollReset
                aria-current={active ? "page" : undefined}
                className={`block whitespace-nowrap text-sm ${byApparatus ? "rounded-full px-3 py-1.5" : "rounded-md px-2.5 py-1"} ${
                  active
                    ? "bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900"
                    : byApparatus
                      ? "bg-gray-100 dark:bg-gray-800"
                      : "text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
                }`}
              >
                {member.apparatus ? <ApparatusCode apparatus={member.apparatus} /> : member.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/**
 * The event's other divisions, each opened on the same kind of competition and view where it held
 * one ("Team Final", "UB"), else its first.
 */
export function DivisionNav({ event, discipline, ageCategory, slug, view }: Omit<Where, "athleteId">) {
  if (event.divisions.length < 2) {
    return null;
  }
  const own = event.divisions.find(
    (division) => division.discipline === discipline && division.ageCategory === ageCategory,
  );
  const key = own && tabOf(competitionTabs(own), slug)?.key;
  return (
    <nav aria-label="Divisions">
      <ul className="inline-flex flex-wrap gap-1 rounded-lg border border-gray-200 p-1 dark:border-gray-800">
        {event.divisions.map((division) => {
          const active = division === own;
          const tabs = competitionTabs(division);
          const tab = tabs.find((candidate) => candidate.key === key) ?? tabs[0];
          if (!tab) {
            return null;
          }
          return (
            <li key={`${division.discipline}-${division.ageCategory}`}>
              <Link
                to={path(
                  event,
                  division.discipline,
                  division.ageCategory,
                  memberFor(tab, view),
                  view != null ? { view } : {},
                )}
                preventScrollReset
                aria-current={active ? "page" : undefined}
                className={`block whitespace-nowrap rounded-md px-2.5 py-1 text-sm ${
                  active
                    ? "bg-gray-900 font-semibold text-white dark:bg-gray-100 dark:text-gray-900"
                    : "text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800"
                }`}
              >
                <Division discipline={division.discipline} ageCategory={division.ageCategory} />
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
