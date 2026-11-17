import { type RouteConfig, index, route } from "@react-router/dev/routes";

export default [
  index("routes/events.tsx"),
  route("events/:eventSlug", "routes/event.tsx"),
  route("events/:eventSlug/:discipline/:ageCategory/:sessionSlug", "routes/session.tsx"),
  route("athletes", "routes/athletes.tsx"),
  route("athletes/:athleteId", "routes/athlete.tsx"),
] satisfies RouteConfig;
