import { createFileRoute } from "@tanstack/react-router";
import { Builder } from "@/features/builder";
export const Route = createFileRoute("/outfits/new")({
  head: () => ({
    meta: [
      { title: "Create an outfit · thread" },
      {
        name: "description",
        content:
          "Assemble your outfit step by step and generate front, side and back try-on views.",
      },
      { property: "og:title", content: "Create an outfit · thread" },
      { property: "og:description", content: "Bring your favorite pieces together." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Builder,
});
