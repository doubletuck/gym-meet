import type { Apparatus, DivisionCompetitions } from "~/api/types";

/** One competition (or ranking) a tab opens: an apparatus's final, a round, a part, or the tab's only one. */
export type TabMember = {
  slug: string;
  /** The apparatus, for an apparatus final or an apparatus-format meet's qualification */
  apparatus: Apparatus | null;
  /** "Round 1", "Part 2", "Combined"; empty for an apparatus, shown by its code, or a tab's only member */
  label: string;
};

/**
 * A tab on a division's results: a competition, or competitions read as one, each held on its own
 * apparatus (the apparatus finals), round (a mixed team final) or part (a two-day final).
 */
export type CompetitionTab = {
  /** The same in every division that holds it ("qualification", "C3-apparatus"), to keep the tab on switching */
  key: string;
  label: string;
  members: TabMember[];
  date: string;
  endDate: string | null;
};

const SUFFIX_SLUG = /(-round-\d+)?(-part-\d+)?$/;
const SUFFIX_NAME = /(, Round \d+)?(, Part \d+)?$/;

/**
 * "Qualification" for a Competition I named for the titles it decided and qualified
 * ("All-Around Final · Team and Apparatus Qualification"), else its name.
 */
function tabLabel(name: string, shortName: string): string {
  const base = name.replace(SUFFIX_NAME, "");
  return base.includes(" · ") ? shortName.replace(SUFFIX_NAME, "") : base;
}

/**
 * A division's results as tabs, in the order they're held: a ranking with no competition of its
 * own first, then each competition, with a meet's apparatus finals (or apparatus-format
 * qualification) as one tab, and a competition's rounds or parts as one tab.
 */
export function competitionTabs(division: DivisionCompetitions): CompetitionTab[] {
  const tabs = new Map<string, CompetitionTab>();
  const add = (key: string, label: string, member: TabMember, date: string, endDate: string | null) => {
    const tab = tabs.get(key) ?? { key, label, members: [], date, endDate: null };
    tabs.set(key, tab);
    tab.members.push(member);
    const last = [tab.endDate ?? tab.date, endDate ?? date].sort().at(-1)!;
    tab.date = [tab.date, date].sort()[0];
    tab.endDate = last > tab.date ? last : null;
  };

  for (const ranking of division.rankings) {
    add(
      `ranking-${ranking.slug}`,
      ranking.name,
      { slug: ranking.slug, apparatus: null, label: "" },
      ranking.date,
      ranking.endDate,
    );
  }
  for (const competition of division.competitions) {
    const { slug, name, shortName, type, apparatus, round, part, date, endDate } = competition;
    if (apparatus) {
      // Named for the apparatus as a whole, not its first ("Vault Qualification")
      const label = type === "C3" ? "Apparatus Finals" : shortName.replace(SUFFIX_NAME, "");
      add(`${type}-apparatus`, label, { slug, apparatus, label: "" }, date, endDate);
    } else {
      const label = round != null ? `Round ${round}` : part != null ? `Part ${part}` : "";
      add(slug.replace(SUFFIX_SLUG, ""), tabLabel(name, shortName), { slug, apparatus: null, label }, date, endDate);
    }
  }
  // A split competition's combined row, beside its parts
  for (const tab of tabs.values()) {
    if (tab.members.length > 1) {
      tab.members
        .filter((member) => !member.label && !member.apparatus)
        .forEach((member) => (member.label = "Combined"));
    }
  }
  return [...tabs.values()];
}

/** The tab holding the competition. */
export function tabOf(tabs: CompetitionTab[], slug: string): CompetitionTab | undefined {
  return tabs.find((tab) => tab.members.some((member) => member.slug === slug));
}

/**
 * The member a tab opens on: the apparatus the reader is viewing, so qualification's UB view opens
 * the uneven bars final, else the tab's first.
 */
export function memberFor(tab: CompetitionTab, view: string | null): TabMember {
  return tab.members.find((member) => member.apparatus != null && member.apparatus === view) ?? tab.members[0];
}
