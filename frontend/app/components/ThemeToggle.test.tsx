import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { themeScript } from "~/lib/theme";
import { ThemeToggle } from "./ThemeToggle";

let systemDark = false;
const listeners = new Set<() => void>();

beforeEach(() => {
  systemDark = false;
  localStorage.clear();
  document.documentElement.classList.remove("dark");
  vi.stubGlobal("matchMedia", () => ({
    get matches() {
      return systemDark;
    },
    addEventListener: (_: string, listener: () => void) => listeners.add(listener),
    removeEventListener: (_: string, listener: () => void) => listeners.delete(listener),
  }));
});

afterEach(() => {
  listeners.clear();
  vi.unstubAllGlobals();
});

const isDark = () => document.documentElement.classList.contains("dark");

describe("ThemeToggle", () => {
  it("follows the system until a theme is picked", () => {
    systemDark = true;
    render(<ThemeToggle />);

    expect(screen.getByRole("button", { name: "System theme" })).toHaveAttribute("aria-pressed", "true");
    expect(isDark()).toBe(true);

    systemDark = false;
    listeners.forEach((listener) => listener());
    expect(isDark()).toBe(false);
  });

  it("keeps a picked theme over the system's, and remembers it", () => {
    systemDark = true;
    render(<ThemeToggle />);

    fireEvent.click(screen.getByRole("button", { name: "Light theme" }));

    expect(isDark()).toBe(false);
    expect(localStorage.getItem("theme")).toBe("light");
    expect(listeners.size).toBe(0);
  });

  it("starts from the remembered theme", () => {
    localStorage.setItem("theme", "dark");
    render(<ThemeToggle />);

    expect(screen.getByRole("button", { name: "Dark theme" })).toHaveAttribute("aria-pressed", "true");
    expect(isDark()).toBe(true);
  });

  it("forgets the choice when set back to system", () => {
    localStorage.setItem("theme", "dark");
    render(<ThemeToggle />);

    fireEvent.click(screen.getByRole("button", { name: "System theme" }));

    expect(localStorage.getItem("theme")).toBeNull();
    expect(isDark()).toBe(false);
  });
});

describe("themeScript", () => {
  it("applies a remembered dark theme before the page paints", () => {
    localStorage.setItem("theme", "dark");
    new Function(themeScript)();
    expect(isDark()).toBe(true);
  });

  it("keeps a remembered light theme over a dark system", () => {
    systemDark = true;
    localStorage.setItem("theme", "light");
    new Function(themeScript)();
    expect(isDark()).toBe(false);
  });
});
