export type ThemeChoice = "system" | "light" | "dark";

const storageKey = "theme";
const darkQuery = "(prefers-color-scheme: dark)";

/** The visitor's saved choice; "system" when none is saved or storage is blocked. */
export function readThemeChoice(): ThemeChoice {
  try {
    const saved = localStorage.getItem(storageKey);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    // Storage blocked (private window, site data off): follow the system
  }
  return "system";
}

export function saveThemeChoice(choice: ThemeChoice) {
  try {
    if (choice === "system") localStorage.removeItem(storageKey);
    else localStorage.setItem(storageKey, choice);
  } catch {
    // The choice still applies to this visit
  }
}

export function systemDarkQuery(): MediaQueryList | undefined {
  return window.matchMedia?.(darkQuery);
}

/** Puts the `dark` class, which Tailwind's `dark:` styles key on, on the page when the choice resolves to dark. */
export function applyTheme(choice: ThemeChoice) {
  const dark = choice === "dark" || (choice === "system" && (systemDarkQuery()?.matches ?? false));
  document.documentElement.classList.toggle("dark", dark);
}

// Runs in the page's head before it paints, so a saved light or dark choice shows without a flash of the other.
// Kept in step with readThemeChoice and applyTheme by hand.
export const themeScript = `(function () {
  var c = null;
  try { c = localStorage.getItem("${storageKey}"); } catch (e) {}
  var dark = c === "dark" || (c !== "light" && window.matchMedia && window.matchMedia("${darkQuery}").matches);
  if (dark) document.documentElement.classList.add("dark");
})();`;
