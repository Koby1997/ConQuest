---
name: discover
description: Research upcoming conventions, expos, maker faires, science/tech events and film-in-concert shows within driving range of home, and save them into the ConQuest app. Use when the user runs /discover (optionally with seed, refresh, rescore, or a category word like maker, space, comic, film).
argument-hint: "[seed | refresh | rescore | <category word>]"
---

# /discover: find events and save them to ConQuest

You are the research half of ConQuest. The app (Python, in this folder) stores and ranks events;
you find them on the web and hand them over as a JSON file. Arguments: `$ARGUMENTS`

Run every command from the project root with the project's virtualenv:
`.venv/Scripts/python -m conquest <command>`

## 1. Decide the mode

| Arguments | Mode | What to do |
|---|---|---|
| (empty) | `rotation` | Search the categories in `suggested_next` across its regions. |
| a category word (`maker`, `space`, `comic`, `film`, `robots`...) | `category` | Run `context --category <word>`, search that category across all regions. |
| `seed` | `seed` | First big run: any events named in the interest profile, then the two most overdue categories. Tell the user that later `/discover` runs will cover the rest. |
| `refresh` | `refresh` | Only check the events in `needs_date_check` (official sites first). No broad searching. |
| `rescore` | `rescore` | No web searches. Run `context --details` and re-score every known event against the interest profile. |

## 2. Read the context

Run `.venv/Scripts/python -m conquest context` (add `--category <word>` or `--details` as above).
It gives you:
- `today`, the `home` location and the `drive_limits_minutes` per size tier,
- the `interest_profile` written by the user,
- `known_series`: events already saved, with ids, aliases, cities and next dates,
- `needs_date_check`: known events without confirmed upcoming dates,
- `needs_ai_review`: events imported from Ticketmaster that need categories and a score,
- `suggested_next`: which categories and regions are due.

Use `known_series` to recognise events you find again. When something you find is already
there, put its `id` in `matches_existing_series_id`. Never create a second entry for it.

## 3. Research

Keep each session small so it doesn't use too much of the user's plan: aim for roughly 15-25 web searches,
and stop and import what you have rather than going much further.

For each category x region pair:
- Search for the upcoming events (e.g. "maker faire Tampa 2027", "comic con Jacksonville 2027",
  "film in concert orchestra Orlando 2027", "science center adult night Orlando"). Try the
  region's big venues and con-listing sites too.
- **Regions far from `home`: only look for events big enough to be worth the drive.** Compare the
  rough drive to `drive_limits_minutes`: if a region is beyond the `regional` limit, search it for
  `major` events only, and don't bother with local talks there.
- Open the official event site for each promising result to confirm dates, venue and ticket prices.
  Official sites beat aggregators; aggregators are often stale.
- Make sure the dates are for the *next* edition, not last year's. If the next dates aren't announced,
  add an occurrence with `date_status: "estimated"`, a best-guess date from past years, and
  `usual_months`.
- Look for what attendees say: Reddit threads, blog write-ups, local news coverage of past years.
  Summarise it honestly in `review_summary` (2-3 sentences), with pros and cons, and link the sources
  in `review_sources`. If you found nothing, leave `review_summary` out. Don't invent reviews.
- **Never guess prices.** If prices aren't published yet, leave `price_min` and `price_max` out and say
  so in `price_notes` (e.g. "2026 prices were $35/day; 2027 not announced").
- Every event must have evidence: a `website` and/or `source_urls` you actually read.

In seed mode, first research any specific events the `interest_profile` names (e.g. "Otronicon",
"MegaCon"), unless they're already in `known_series`. If one has been renamed, record the current
name with `rename: true` and the old name in `aliases`. If it has ended for good, mark it
`active: false`. Then move on to the category searches.

### Choosing fields

- `categories` (1-4): `comic_pop`, `anime_gaming`, `tech`, `maker`, `space_science`, `engineering`,
  `film_music`, `talks`, `museum`, `other`.
- `size_tier`: `local` = a talk, meetup or small show (a few hundred people); `regional` = a science
  center event, film-in-concert, maker faire or mid-size con; `major` = a big multi-day convention
  that draws people from out of state.
- `recurrence`: `annual`, `multiple_per_year` (e.g. a monthly lecture series), `one_time`, `unknown`.
- `ai_interest_score` (0-100), judged against the `interest_profile`: 90+ = exactly what they
  described; 70-89 = a strong fit; 50-69 = might enjoy it; below 50 = probably not. Give a one-line
  `interest_reason`.
- Don't include events the profile clearly rules out just to fill the list. Do include near misses
  that score 40-60. The app sorts them lower rather than hiding them.

## 4. Write the findings file

Write `data/inbox/<YYYY-MM-DD-HHMM>-<mode>.json`. Run `.venv/Scripts/python -m conquest schema` if you need the full
format. The shape is:

```json
{
  "mode": "rotation",
  "categories_searched": ["maker", "space_science"],
  "regions_searched": ["Central Florida", "Tampa Bay", "Northeast Florida", "South Florida"],
  "notes": "Anything worth remembering for next time (e.g. 'X hasn't announced 2027 dates yet').",
  "series": [
    {
      "matches_existing_series_id": null,
      "name": "Orlando Maker Faire",
      "aliases": [],
      "website": "https://...",
      "categories": ["maker", "engineering"],
      "size_tier": "regional",
      "recurrence": "annual",
      "usual_months": [11],
      "description": "2-4 sentences: what it is and what you do there.",
      "review_summary": "What attendees say.",
      "review_pros": ["..."],
      "review_cons": ["..."],
      "review_sources": ["https://..."],
      "ai_interest_score": 92,
      "interest_reason": "Maker faires are a stated favourite.",
      "occurrences": [
        {
          "start_date": "2027-11-13",
          "end_date": "2027-11-14",
          "date_status": "confirmed",
          "venue_name": "...",
          "address": "street, city, ST zip",
          "city": "Orlando",
          "state": "FL",
          "price_min": 15,
          "price_max": 40,
          "price_notes": "$15 kids, $25 adults, $40 weekend",
          "ticket_url": "https://...",
          "source_urls": ["https://..."]
        }
      ]
    }
  ],
  "score_updates": []
}
```

- For `rescore`, and for anything in `needs_ai_review`, use `score_updates`:
  `{"series_id": 12, "ai_interest_score": 75, "interest_reason": "...", "categories": [...], "size_tier": "regional"}`.
- `regions_searched` must use the exact region names from the context.
- Only list the categories and regions you actually searched. The rotation relies on it.

## 5. Import

Run `.venv/Scripts/python -m conquest import data/inbox/<file>.json`.
- If it prints `NOT imported` with a list of problems, fix those fields in the file and run the import again.
  Nothing is saved until the whole file is valid.
- On success the file moves to `data/inbox/imported/`, and the command prints what was new, updated or confirmed.

## 6. Tell the user

Give a short summary:
- the new events worth a look (name, dates, city, price),
- events that just announced dates,
- anything notable (an event renamed or ended, a sold-out risk),
- what the next `/discover` will cover (the next categories in the rotation).

Remind them the events are in the app at http://127.0.0.1:8000 (start it with `.venv/Scripts/python run_api.py`).
