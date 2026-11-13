import { createFileRoute } from "@tanstack/react-router";
import { Wardrobe } from "@/features/wardrobe";
export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "thread · Your personal fitting room" },
      {
        name: "description",
        content:
          "Bring your wardrobe together and explore outfits with a personal virtual fitting room.",
      },
      { property: "og:title", content: "thread · Your personal fitting room" },
      {
        property: "og:description",
        content: "Explore the possibilities in the wardrobe you already love.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Wardrobe,
});
