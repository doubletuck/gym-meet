import { queryOptions, QueryClient } from "@tanstack/react-query";
import createClient from "openapi-fetch";
import { data } from "react-router";
import type { paths } from "./schema";

const api = createClient<paths>({ baseUrl: "" });

// Responses change only when results are imported; the API caches them for 5 minutes too
export const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 5 * 60 * 1000 } },
});

/**
 * The response's data, or a thrown route error the page's error boundary
 * shows: "not found" for a 404, a general error otherwise.
 */
function orThrow<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data === undefined) {
    throw data(null, { status: result.response.status, statusText: result.response.statusText });
  }
  return result.data;
}

export const eventsQuery = () =>
  queryOptions({
    queryKey: ["events"],
    queryFn: async () => orThrow(await api.GET("/api/events")),
  });

export const eventQuery = (slug: string) =>
  queryOptions({
    queryKey: ["events", slug],
    queryFn: async () => orThrow(await api.GET("/api/events/{slug}", { params: { path: { slug } } })),
  });

export const athleteSearchQuery = (q: string) =>
  queryOptions({
    queryKey: ["athletes", "search", q],
    queryFn: async () => orThrow(await api.GET("/api/athletes", { params: { query: { q } } })),
  });

export const athleteQuery = (id: number) =>
  queryOptions({
    queryKey: ["athletes", id],
    queryFn: async () => orThrow(await api.GET("/api/athletes/{id}", { params: { path: { id } } })),
  });

export const sessionResultsQuery = (id: number) =>
  queryOptions({
    queryKey: ["sessions", id, "results"],
    queryFn: async () => orThrow(await api.GET("/api/sessions/{id}/results", { params: { path: { id } } })),
  });
