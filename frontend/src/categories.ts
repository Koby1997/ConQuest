// One colour per category, used for card stripes and chips. Chosen to stay
// distinguishable from each other on the dark background.
export const CATEGORY_COLORS: Record<string, string> = {
  comic_pop: "#f87171",
  anime_gaming: "#f472b6",
  tech: "#60a5fa",
  maker: "#fbbf24",
  space_science: "#a78bfa",
  engineering: "#2dd4bf",
  film_music: "#fb923c",
  talks: "#4ade80",
  museum: "#22d3ee",
  other: "#94a3b8",
};

export const CATEGORY_ICONS: Record<string, string> = {
  comic_pop: "🦸",
  anime_gaming: "🎮",
  tech: "💻",
  maker: "🛠️",
  space_science: "🚀",
  engineering: "🤖",
  film_music: "🎻",
  talks: "🎤",
  museum: "🏛️",
  other: "✨",
};

export const colorFor = (category: string | undefined): string =>
  CATEGORY_COLORS[category ?? "other"] ?? CATEGORY_COLORS.other;

export const SIZE_LABELS: Record<string, string> = {
  local: "Local",
  regional: "Regional",
  major: "Major",
};
