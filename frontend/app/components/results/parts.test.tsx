import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Country } from "./parts";

describe("Country", () => {
  it("names the country after its flag", () => {
    const { container } = render(<Country noc="USA" />);

    expect(container).toHaveTextContent("United States");
    expect(container.querySelector("img")).toHaveAttribute("alt", "");
  });

  it("names the club in place of the country, which the flag stands for", () => {
    const { container } = render(<Country noc="USA" club="U of Michigan" />);

    expect(container).toHaveTextContent(/^U of Michigan$/);
    expect(screen.getByRole("img", { name: "United States" })).toHaveAttribute("title", "United States");
  });

  it("names the country after the club when there's no flag to stand for it", () => {
    const { container } = render(<Country noc="AIN1" club="Club X" />);

    expect(container).toHaveTextContent("Club X · Individual Neutral Athletes (AIN1)");
  });
});
