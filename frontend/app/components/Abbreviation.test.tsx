import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Abbreviation, ApparatusCode } from "./Abbreviation";

describe("ApparatusCode", () => {
  it("shows the code, with the full name as a tooltip and for screen readers", () => {
    render(<ApparatusCode apparatus="PH" />);

    const abbr = screen.getByTitle("Pommel Horse");
    expect(screen.getByText("PH")).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByText("Pommel Horse")).toHaveClass("sr-only");
    expect(abbr).toContainElement(screen.getByText("PH"));
  });

  it("numbers a vault", () => {
    render(<ApparatusCode apparatus="VT" routine={2} />);

    expect(screen.getByTitle("Vault 2")).toBeInTheDocument();
    expect(screen.getByText("VT2")).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByText("Vault 2")).toHaveClass("sr-only");
  });
});

describe("Abbreviation", () => {
  it("leaves the short form alone unless it's spoken", () => {
    render(<Abbreviation short="D" label="Difficulty" />);

    expect(screen.getByTitle("Difficulty")).toHaveTextContent(/^D$/);
  });
});
