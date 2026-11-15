import { type RouteConfig, index, route } from "@react-router/dev/routes";

export default [
  index("routes/events.tsx"),
  route("events/:eventSlug", "routes/event.tsx"),
  route("events/:eventSlug/:discipline/:ageCategory/:sessionSlug", "routes/session.tsx"),
] satisfies RouteConfig;
