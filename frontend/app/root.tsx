import { QueryClientProvider } from "@tanstack/react-query";
import { isRouteErrorResponse, Link, Links, Meta, NavLink, Outlet, Scripts, ScrollRestoration } from "react-router";

import type { Route } from "./+types/root";
import { queryClient } from "./api/client";
import "./app.css";

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <Meta />
        <Links />
      </head>
      <body className="min-h-screen antialiased">
        {children}
        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Shell>
        <Outlet />
      </Shell>
    </QueryClientProvider>
  );
}

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  isActive
    ? "font-medium text-gray-900 dark:text-gray-100"
    : "text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100";

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <>
      <header className="border-b border-gray-200 dark:border-gray-800">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
          <Link to="/" className="text-lg font-semibold tracking-tight">
            Gym Meet
          </Link>
          <nav aria-label="Main">
            <ul className="flex gap-4 text-sm">
              <li>
                <NavLink to="/" end className={navLinkClass}>
                  Competitions
                </NavLink>
              </li>
              <li>
                <NavLink to="/athletes" className={navLinkClass}>
                  Athletes
                </NavLink>
              </li>
            </ul>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">{children}</main>
    </>
  );
}

export function HydrateFallback() {
  return (
    <Shell>
      <p className="text-gray-500">Loading…</p>
    </Shell>
  );
}

export function ErrorBoundary({ error }: Route.ErrorBoundaryProps) {
  let message = "Something went wrong";
  let details = "The page couldn't be loaded. Try again in a moment.";
  let stack: string | undefined;

  if (isRouteErrorResponse(error) && error.status === 404) {
    message = "Not found";
    details = "There's no page at this address.";
  } else if (import.meta.env.DEV && error instanceof Error) {
    details = error.message;
    stack = error.stack;
  }

  return (
    <Shell>
      <h1 className="text-2xl font-semibold">{message}</h1>
      <p className="mt-2 text-gray-600 dark:text-gray-400">{details}</p>
      <p className="mt-4">
        <Link to="/" className="text-blue-700 underline dark:text-blue-400">
          See all competitions
        </Link>
      </p>
      {stack && (
        <pre className="mt-4 w-full overflow-x-auto p-4 text-xs">
          <code>{stack}</code>
        </pre>
      )}
    </Shell>
  );
}
