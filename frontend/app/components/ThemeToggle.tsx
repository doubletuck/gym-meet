import { useEffect, useState } from "react";

import { applyTheme, readThemeChoice, saveThemeChoice, systemDarkQuery, type ThemeChoice } from "~/lib/theme";

const options: { choice: ThemeChoice; label: string; icon: React.ReactNode }[] = [
  {
    choice: "system",
    label: "System theme",
    icon: (
      <>
        <rect x="3" y="4" width="18" height="12" rx="1.5" />
        <path d="M8 20h8M12 16v4" />
      </>
    ),
  },
  {
    choice: "light",
    label: "Light theme",
    icon: (
      <>
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
      </>
    ),
  },
  {
    choice: "dark",
    label: "Dark theme",
    icon: <path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5Z" />,
  },
];

export function ThemeToggle() {
  // Unknown until mounted: the page is pre-rendered without access to the visitor's saved choice
  const [choice, setChoice] = useState<ThemeChoice | null>(null);

  useEffect(() => {
    if (choice === null) {
      setChoice(readThemeChoice());
      return;
    }
    applyTheme(choice);
    if (choice !== "system") return;

    const query = systemDarkQuery();
    const follow = () => applyTheme("system");
    query?.addEventListener("change", follow);
    return () => query?.removeEventListener("change", follow);
  }, [choice]);

  const choose = (next: ThemeChoice) => {
    saveThemeChoice(next);
    setChoice(next);
  };

  return (
    <div role="group" aria-label="Theme" className="flex rounded-md border border-gray-200 p-0.5 dark:border-gray-800">
      {options.map((option) => (
        <button
          key={option.choice}
          type="button"
          aria-label={option.label}
          aria-pressed={choice === option.choice}
          title={option.label}
          onClick={() => choose(option.choice)}
          className={
            choice === option.choice
              ? "rounded bg-gray-200 p-1 text-gray-900 dark:bg-gray-800 dark:text-gray-100"
              : "rounded p-1 text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
          }
        >
          <svg
            viewBox="0 0 24 24"
            className="size-4"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            {option.icon}
          </svg>
        </button>
      ))}
    </div>
  );
}
