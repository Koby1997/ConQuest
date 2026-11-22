# ConQuest

Find conventions, expos, maker faires, science and tech events, and film-in-concert shows
*before* they happen, within a realistic drive of home.

ConQuest has two halves:

- **The app** (this repo): a local web page that stores events and ranks them by your interests.
  It shows dates, prices, drive time and what people say, and keeps your list of what you're
  going to. It contains no AI and costs nothing to run.
- **The `/discover` skill** (`.claude/skills/discover/SKILL.md`): Claude Code searches the web for
  events and saves them into the app. It runs on your Claude plan, with no API key and no extra
  charges.

## First-time setup

You need Python 3.11+, Node.js 22+, and [Claude Code](https://claude.com/claude-code) for `/discover`.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
cd frontend
npm install
npm run build
```

### Make it yours

1. **Home:** copy `.env.example` to `.env` and set your city and its coordinates *before* the first
   run. Drive times are measured from there. (You can also change it later in **Settings**.)
2. **Interests:** in **Settings → What you're into**, describe what you like in your own words, and
   name specific events you already know you love. `/discover` scores every event against this,
   and `/discover seed` looks up the named events first.
3. **Regions:** the search regions are Florida's (Central Florida, Tampa Bay, Northeast Florida,
   South Florida). If you live elsewhere, edit `REGIONS` in `conquest/categories.py`.

## Using it

**Look at events:**

```powershell
.venv\Scripts\python run_api.py
```

Then open http://127.0.0.1:8000.

**Find more events:** open this folder in VS Code, open the Claude Code panel, and type one of:

| Command | What it does |
|---|---|
| `/discover seed` | The first big search |
| `/discover` | The next couple of categories in the rotation. Good once a week. |
| `/discover maker` | One category (also `space`, `comic`, `anime`, `tech`, `robots`, `film`, `talks`, `museum`) |
| `/discover refresh` | Check events you already have for newly announced dates |
| `/discover rescore` | Re-score everything after you change your interests in Settings |

Each run finishes with a summary of what's new. Click ⟳ in the app to see it.

**Plan what to go to:**

- **Upcoming:** switch between ⭐ *Best match* and 📅 *Soonest first* (closest dates first, grouped by
  month). Every card says how far away it is ("In 3 months").
- **📅 Add to my calendar** on any card puts the event on *My calendar*. *Going (got tickets)* in an
  event's details does the same.
- **Calendar:** a month view that switches between *All events* and *My calendar*, with that month's
  events listed underneath in date order.
- **Export:** *⬇ Export (.ics)* on My calendar or My List downloads a calendar file you can import into
  Google Calendar, Outlook or your phone. Each event's details also have its own .ics download.

## How it fits together

```
/discover (Claude Code)                          the app
  1. python -m conquest context   -> reads what's saved, what's due for a search
  2. web searches, official sites
  3. writes data/inbox/<file>.json
  4. python -m conquest import    -> validates, merges duplicates, finds venues -> data/conquest.db
                                                                          ^
                                         run_api.py + frontend/ read it --+
```

- **Events vs. editions:** "MegaCon Orlando" is one event, and each year's dates are an edition. Once
  an event is known, it is never missed again. Before new dates are announced, it shows as
  "Usually in May". Renamed events keep their old names as aliases (Otronicon is now Spark STEM Fest).
- **Ranking:** each event's score starts with how well Claude judged it fits your interests. A 👍/👎
  on an event moves that event and teaches its categories. You can also boost categories by hand
  in Settings.
- **Drive limits:** each event size has its own limit (defaults: local 1 h, regional 3 h, major 4.5 h).
  Farther events are hidden unless you tick "Include farther events". Drive times are estimated
  from straight-line distance, so your home location is never sent anywhere.
- **Imports are checked:** `conquest import` rejects malformed findings with field-by-field errors,
  and never touches your ratings, status or notes.

## Development

```powershell
.venv\Scripts\python -m pytest                   # backend tests (no network)
.venv\Scripts\python run_api.py --reload         # API with auto-reload
cd frontend; npm run dev                          # UI with hot reload at http://localhost:5173
.venv\Scripts\python -m conquest schema          # the import format as JSON Schema
```

Your data lives in `data/` (git-ignored): `conquest.db`, plus `inbox/imported/` with every findings
file a session produced.

## Planned next

- A "What's New" tab
- Ticketmaster (free API key) for film-in-concert and orchestra shows
- Weekly automatic `/discover` runs (needs the Claude Code CLI and Windows Task Scheduler)
- Trip planning for other cities a year ahead

## License

MIT. See [LICENSE](LICENSE).
