import { createFileRoute } from "@tanstack/react-router";
import { Compare } from "@/features/outfits";
export const Route = createFileRoute("/compare")({
  validateSearch: (s: Record<string, unknown>): { a?: string; b?: string; debug?: string } => ({
    a: typeof s.a === "string" ? s.a : undefined,
    b: typeof s.b === "string" ? s.b : undefined,
    debug: typeof s.debug === "string" ? s.debug : undefined,
  }),
  head: () => ({
    meta: [
      { title: "Compare your looks · thread" },
      {
        name: "description",
        content: "Compare two saved outfits, view by view, to find your favorite combination.",
      },
      { property: "og:title", content: "Compare your looks · thread" },
      { property: "og:description", content: "Two looks. A fresh perspective." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Comparison,
});
function Comparison() {
  const { a, b } = Route.useSearch();
  return <Compare a={a} b={b} />;
}
