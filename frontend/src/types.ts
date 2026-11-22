// Shapes returned by the FastAPI server (conquest/api.py).

export type Status = "none" | "interested" | "going" | "went" | "skip";
export type Rating = -1 | 0 | 1;

export interface Occurrence {
  id: number;
  start_date: string;
  end_date: string | null;
  date_status: "confirmed" | "estimated" | string;
  venue_name: string | null;
  address: string | null;
  city: string;
  state: string;
  price_min: number | null;
  price_max: number | null;
  price_notes: string | null;
  ticket_url: string | null;
  source_urls: string[];
  drive_minutes: number | null;
  last_verified: string | null;
}

export interface EventCard {
  id: number;
  name: string;
  aliases: string[];
  categories: string[];
  size_tier: string;
  recurrence: string;
  usual_months: number[];
  active: boolean;
  description: string;
  website: string | null;
  ai_interest_score: number | null;
  interest_reason: string | null;
  match_score: number;
  rating: Rating;
  status: Status;
  notes: string;
  is_new: boolean;
  first_seen: string;
  next: Occurrence | null;
  expected_month: number | null;
  drive_minutes: number | null;
  drive_limit: number;
  within_range: boolean | null;
  has_reviews: boolean;
}

export interface EventDetail extends EventCard {
  review_summary: string | null;
  review_pros: string[];
  review_cons: string[];
  review_sources: string[];
  occurrences: Occurrence[];
  last_checked: string | null;
}

export interface EventUpdate {
  rating?: Rating;
  status?: Status;
  notes?: string;
}

export interface Meta {
  categories: Record<string, string>;
  size_tiers: Record<string, string>;
  regions: string[];
  statuses: Record<string, string>;
  recurrences: Record<string, string>;
  total_events: number;
}

export interface Settings {
  home_label: string;
  home_lat: number;
  home_lng: number;
  drive_limits: Record<string, number>;
  interest_profile: string;
  category_boosts: Record<string, number>;
  learned_category_points: Record<string, number>;
  last_seen_new_at: string | null;
}

export interface SettingsUpdate {
  home_label?: string;
  drive_limits?: Record<string, number>;
  interest_profile?: string;
  category_boosts?: Record<string, number>;
}

/** One edition of one event, for the calendar. */
export interface CalendarEntry {
  occurrence_id: number;
  series_id: number;
  name: string;
  categories: string[];
  size_tier: string;
  status: Status;
  rating: Rating;
  match_score: number;
  active: boolean;
  start_date: string;
  end_date: string | null;
  date_status: string;
  venue_name: string | null;
  city: string;
  state: string;
  price_min: number | null;
  price_max: number | null;
  drive_minutes: number | null;
  within_range: boolean | null;
}

/** Statuses that put an event on "My calendar". */
export const CHOSEN: Status[] = ["interested", "going"];
export const isChosen = (status: Status): boolean => CHOSEN.includes(status);

export interface DiscoveryRun {
  id: number;
  mode: string;
  source: string;
  categories: string[];
  regions: string[];
  notes: string | null;
  new_series: number;
  updated_series: number;
  new_occurrences: number;
  updated_occurrences: number;
  created_at: string;
}
