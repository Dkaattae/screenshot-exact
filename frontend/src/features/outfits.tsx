import { useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Heart, Trash2, Columns2, ArrowUpRight, Layers, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/api/client";
import { VIEWS } from "@/api/rules";
import type { Outfit, View } from "@/api/types";
import { outfitsQuery, jobsQuery } from "./queries";
import { Heading, Confirm, ResourceImage, QueryError, LoadingGrid } from "./common";
import { toast } from "sonner";
export function Outfits() {
  const { data: outfits = [], isLoading, error } = useQuery(outfitsQuery);
  const [favorites, setFavorites] = useState(false);
  const [remove, setRemove] = useState<Outfit>();
  const client = useQueryClient();
  const del = useMutation({
    mutationFn: (id: string) => api.deleteOutfit(id),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["outfits"] });
      setRemove(undefined);
      toast.success("Outfit deleted.");
    },
    onError: (e) => toast.error(e.message),
  });
  return (
    <div className="page-container">
      <Heading
        eyebrow="LOOKS TO COME BACK TO"
        title="Your outfits"
        description="The combinations you love, all in one place."
        action={
          <Button asChild size="lg">
            <Link to="/outfits/new">
              <Plus />
              New outfit
            </Link>
          </Button>
        }
      />
      <div className="collection-controls">
        <div className="segmented">
          <Button variant={favorites ? "ghost" : "secondary"} onClick={() => setFavorites(false)}>
            All outfits <span>{outfits.length}</span>
          </Button>
          <Button variant={favorites ? "secondary" : "ghost"} onClick={() => setFavorites(true)}>
            <Heart />
            Favorites
          </Button>
        </div>
      </div>
      {error ? (
        <QueryError error={error} />
      ) : isLoading ? (
        <LoadingGrid />
      ) : !outfits.filter((o) => !favorites || o.favorite).length ? (
        <div className="empty-state large-empty">
          <Layers />
          <h2>{favorites ? "Your favorites live here." : "A new look is waiting."}</h2>
          <p>
            {favorites
              ? "Save a favorite from any outfit."
              : "Start with a few pieces and see them in a new light."}
          </p>
          <Button asChild>
            <Link to="/outfits/new">
              <Sparkles />
              Create your first outfit
            </Link>
          </Button>
        </div>
      ) : (
        <div className="wardrobe-grid">
          {outfits
            .filter((o) => !favorites || o.favorite)
            .map((o) => (
              <OutfitCard key={o.id} outfit={o} onDelete={() => setRemove(o)} />
            ))}
        </div>
      )}
      <Confirm
        open={!!remove}
        title={`Delete ${remove?.name || "this outfit"}?`}
        onClose={() => setRemove(undefined)}
        onConfirm={() => remove && del.mutate(remove.id)}
      />
    </div>
  );
}
function OutfitCard({ outfit: o, onDelete }: { outfit: Outfit; onDelete: () => void }) {
  const { data: jobs = [] } = useQuery(jobsQuery(o.id));
  const latest = jobs.find((j) => j.views.front.url);
  const client = useQueryClient();
  const fav = useMutation({
    mutationFn: () => api.updateOutfit(o.id, { favorite: !o.favorite }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["outfits"] }),
    onError: (e) => toast.error(e.message),
  });
  return (
    <article className="item-card">
      <Link to="/outfits/$id" params={{ id: o.id }} className="outfit-card-image">
        {latest?.views.front.url ? (
          <ResourceImage
            src={latest.views.front.url}
            alt={o.name || "Saved outfit front view"}
            resource="jobs"
          />
        ) : (
          <div className="outfit-placeholder">
            <ShirtIcon />
            <span>{jobs[0]?.status || "No try-on yet"}</span>
          </div>
        )}
      </Link>
      <div className="item-info">
        <div>
          <h3>{o.name || "Untitled outfit"}</h3>
          <p>
            {new Date(o.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}{" "}
            · Version {o.version}
          </p>
        </div>
        <Button
          variant="ghost"
          size="icon"
          aria-label={o.favorite ? "Remove favorite" : "Favorite outfit"}
          onClick={() => fav.mutate()}
          className={o.favorite ? "favorite" : ""}
        >
          <Heart fill={o.favorite ? "currentColor" : "none"} />
        </Button>
      </div>
      <div className="outfit-card-actions">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/compare" search={{ a: o.id }}>
            <Columns2 />
            Compare
          </Link>
        </Button>
        <Button variant="ghost" size="icon" aria-label="Delete outfit" onClick={onDelete}>
          <Trash2 />
        </Button>
      </div>
    </article>
  );
}
function ShirtIcon() {
  return <Layers size={32} />;
}
export function Compare({ a, b }: { a?: string; b?: string }) {
  const { data: outfits = [] } = useQuery(outfitsQuery);
  const [view, setView] = useState<View>("front");
  const navigate = useNavigate();
  const update = (side: "a" | "b", id: string) =>
    navigate({ to: "/compare", search: { a, b, [side]: id } });
  return (
    <div className="page-container">
      <Heading
        eyebrow="A SECOND PERSPECTIVE"
        title="Side by side"
        description="Same pieces or a new direction? Find the look that feels right."
      />
      <div className="compare-toolbar">
        <div className="segmented">
          {VIEWS.map((v) => (
            <Button
              key={v}
              variant={v === view ? "secondary" : "ghost"}
              className="capitalize"
              onClick={() => setView(v)}
            >
              {v}
            </Button>
          ))}
        </div>
      </div>
      <div className="compare-grid">
        {(["a", "b"] as const).map((s) => (
          <section key={s}>
            <label className="field-label">
              {s === "a" ? "First outfit" : "Second outfit"}
              <select value={(s === "a" ? a : b) || ""} onChange={(e) => update(s, e.target.value)}>
                <option value="">Choose an outfit</option>
                {outfits.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name || "Untitled outfit"} · {new Date(o.created_at).toLocaleDateString()}
                  </option>
                ))}
              </select>
            </label>
            <CompareImage id={s === "a" ? a : b} view={view} />
          </section>
        ))}
      </div>
    </div>
  );
}
function CompareImage({ id, view }: { id?: string; view: View }) {
  const { data: jobs = [] } = useQuery({ ...jobsQuery(id || ""), enabled: !!id });
  const latest = jobs.find((j) => j.views[view].url);
  return (
    <div className="compare-image">
      {latest?.views[view].url ? (
        <ResourceImage src={latest.views[view].url} alt={`${view} comparison`} resource="jobs" />
      ) : (
        <div className="empty-state">
          <Columns2 />
          <p>{id ? "No result for this view yet." : "Choose a look to compare."}</p>
        </div>
      )}
    </div>
  );
}
