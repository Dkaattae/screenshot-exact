import { createFileRoute } from "@tanstack/react-router";
import { Wardrobe } from "@/features/wardrobe";
export const Route = createFileRoute("/wardrobe")({
  head: () => ({
    meta: [
      { title: "Your wardrobe · thread" },
      {
        name: "description",
        content: "Your personal collection of clothing, ready for virtual try-on.",
      },
      { property: "og:title", content: "Your wardrobe · thread" },
      {
        property: "og:description",
        content: "Your favorite pieces, together in one personal wardrobe.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Wardrobe,
});
