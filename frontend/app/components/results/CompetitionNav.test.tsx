import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import type { Apparatus, Discipline } from "~/api/types";
import { competition, division, event } from "~/test/fixtures";
import { CompetitionNav, DivisionNav } from "./CompetitionNav";

function championship(discipline: Discipline, apparatus: Apparatus[], allAroundFinal = true) {
  return division(
    [
      competition({ discipline, slug: "qualification", name: "Qualification" }),
      competition({ discipline, slug: "team-final", name: "Team Final", type: "C4" }),
      ...(allAroundFinal
        ? [competition({ discipline, slug: "all-around-final", name: "All-Around Final", type: "C2" })]
        : []),
      ...apparatus.map((code) =>
        competition({
          discipline,
          slug: `${code.toLowerCase()}-final`,
          name: `${code} Final`,
          type: "C3",
          apparatus: code,
        }),
      ),
    ],
    [],
    { discipline },
  );
}

const worlds = event([
  championship("WAG", ["VT", "UB", "BB", "FX"], false),
  championship("MAG", ["FX", "PH", "SR", "VT", "PB", "HB"]),
]);

function links(name: string) {
  return within(screen.getByRole("navigation", { name })).getAllByRole("link");
}

describe("CompetitionNav", () => {
  it("links each of the division's competitions, keeping the view and the highlighted athlete", () => {
    render(
      <MemoryRouter>
        <CompetitionNav
          event={worlds}
          discipline="WAG"
          ageCategory="SR"
          slug="qualification"
          view="teams"
          athleteId={7}
        />
      </MemoryRouter>,
    );

    const tabs = links("Competitions");
    expect(tabs.map((tab) => tab.firstChild?.textContent)).toEqual(["Qualification", "Team Final", "Apparatus Finals"]);
    expect(tabs[0]).toHaveAttribute("aria-current", "page");
    expect(tabs[1]).toHaveAttribute("href", "/events/2026-world-championships/wag/sr/team-final?view=teams&athlete=7");
    expect(screen.queryByRole("navigation", { name: "Apparatus" })).toBeNull();
  });

  it("opens the apparatus finals on the apparatus being viewed", () => {
    render(
      <MemoryRouter>
        <CompetitionNav event={worlds} discipline="WAG" ageCategory="SR" slug="qualification" view="BB" />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: /Apparatus Finals/ })).toHaveAttribute(
      "href",
      "/events/2026-world-championships/wag/sr/bb-final?view=BB",
    );
  });

  it("lists the apparatus finals under their tab", () => {
    render(
      <MemoryRouter>
        <CompetitionNav event={worlds} discipline="MAG" ageCategory="SR" slug="sr-final" view="SR" athleteId={7} />
      </MemoryRouter>,
    );

    expect(links("Competitions")[3]).toHaveAttribute("aria-current", "page");
    const apparatus = links("Apparatus");
    expect(apparatus.map((link) => link.querySelector("[aria-hidden]")?.textContent)).toEqual([
      "FX",
      "PH",
      "SR",
      "VT",
      "PB",
      "HB",
    ]);
    expect(apparatus[2]).toHaveAttribute("aria-current", "page");
    expect(apparatus[5]).toHaveAttribute("href", "/events/2026-world-championships/mag/sr/hb-final?athlete=7");
  });

  it("shows nothing for a division with one competition", () => {
    const meet = event([
      division([competition({ slug: "team-and-all-around-final", name: "Team and All-Around Final" })]),
    ]);
    const { container } = render(
      <MemoryRouter>
        <CompetitionNav event={meet} discipline="WAG" ageCategory="SR" slug="team-and-all-around-final" view={null} />
      </MemoryRouter>,
    );

    expect(container).toBeEmptyDOMElement();
  });
});

describe("DivisionNav", () => {
  it("opens each division on the same competition and view", () => {
    render(
      <MemoryRouter>
        <DivisionNav event={worlds} discipline="WAG" ageCategory="SR" slug="vt-final" view="VT" />
      </MemoryRouter>,
    );

    const [wag, mag] = links("Divisions");
    expect(wag).toHaveAttribute("aria-current", "page");
    expect(mag).toHaveAttribute("href", "/events/2026-world-championships/mag/sr/vt-final?view=VT");
  });

  it("opens a division that didn't hold the competition on its first", () => {
    render(
      <MemoryRouter>
        <DivisionNav event={worlds} discipline="MAG" ageCategory="SR" slug="all-around-final" view="all-around" />
      </MemoryRouter>,
    );

    expect(links("Divisions")[0]).toHaveAttribute(
      "href",
      "/events/2026-world-championships/wag/sr/qualification?view=all-around",
    );
  });

  it("shows nothing for an event with one division", () => {
    const { container } = render(
      <MemoryRouter>
        <DivisionNav
          event={event([worlds.divisions[0]])}
          discipline="WAG"
          ageCategory="SR"
          slug="qualification"
          view={null}
        />
      </MemoryRouter>,
    );

    expect(container).toBeEmptyDOMElement();
  });
});
