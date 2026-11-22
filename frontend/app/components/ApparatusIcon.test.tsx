import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Apparatus } from "~/api/types";
import { ApparatusIcon } from "./ApparatusIcon";

describe("ApparatusIcon", () => {
  it("draws every apparatus, hidden from screen readers since its code says which it is", () => {
    const apparatus: Apparatus[] = ["VT", "UB", "BB", "FX", "PH", "SR", "PB", "HB"];
    for (const code of apparatus) {
      const { container, unmount } = render(<ApparatusIcon apparatus={code} />);
      const svg = container.querySelector("svg")!;
      expect(svg).toHaveAttribute("aria-hidden");
      expect(svg.querySelector("path")!.getAttribute("d")).not.toBe("");
      unmount();
    }
  });
});
