"""The fixed vocabularies events are described with.

Categories, size tiers and regions are shared by the import format, the
ranking code and the UI, so they live in one place. The slugs are what gets
stored; the labels are what people see.
"""

from __future__ import annotations

CATEGORIES: dict[str, str] = {
    "comic_pop": "Comic & Pop Culture Cons",
    "anime_gaming": "Anime & Gaming",
    "tech": "Tech & Gadgets",
    "maker": "Maker/DIY",
    "space_science": "Space & Science",
    "engineering": "Engineering & Robotics",
    "film_music": "Film & Live Music",
    "talks": "Talks & Lectures",
    "museum": "Museum & Special Events",
    "other": "Other",
}

# Short words people may type after /discover, mapped to a category slug.
CATEGORY_SHORTCUTS: dict[str, str] = {
    "comic": "comic_pop",
    "comics": "comic_pop",
    "con": "comic_pop",
    "cons": "comic_pop",
    "pop": "comic_pop",
    "anime": "anime_gaming",
    "gaming": "anime_gaming",
    "games": "anime_gaming",
    "tech": "tech",
    "maker": "maker",
    "makers": "maker",
    "diy": "maker",
    "space": "space_science",
    "science": "space_science",
    "engineering": "engineering",
    "robotics": "engineering",
    "robots": "engineering",
    "film": "film_music",
    "music": "film_music",
    "orchestra": "film_music",
    "concert": "film_music",
    "talks": "talks",
    "lectures": "talks",
    "museum": "museum",
    "museums": "museum",
}

# How far someone will drive scales with how big the event is. Minutes.
SIZE_TIERS: dict[str, str] = {
    "local": "Local (talk, meetup, small show)",
    "regional": "Regional (science center event, film-in-concert, maker faire)",
    "major": "Major (big multi-day convention)",
}

# Regional is 3 h rather than 2.5 h because the straight-line drive estimate
# runs 10-20% long on straight interstate drives (I-95, the Turnpike), which
# would otherwise push real 2.5 h trips just over the limit.
DEFAULT_DRIVE_LIMITS: dict[str, int] = {
    "local": 60,
    "regional": 180,
    "major": 270,
}

# Regions /discover searches, nearest first. South Florida is only worth it for
# major events given the drive.
REGIONS: list[str] = [
    "Central Florida",
    "Tampa Bay",
    "Northeast Florida",
    "South Florida",
]

# "interested" and "going" are what put an event on "My calendar".
STATUSES: dict[str, str] = {
    "none": "No status",
    "interested": "On my calendar",
    "going": "Going",
    "went": "Went",
    "skip": "Not for me",
}

RECURRENCES: dict[str, str] = {
    "annual": "Every year",
    "multiple_per_year": "Several times a year",
    "one_time": "One time",
    "unknown": "Unknown",
}


def resolve_category(word: str) -> str | None:
    """Turn a slug, label or shortcut word into a category slug, if it is one."""
    key = word.strip().lower()

    if key in CATEGORIES:
        return key
    if key in CATEGORY_SHORTCUTS:
        return CATEGORY_SHORTCUTS[key]
    for slug, label in CATEGORIES.items():
        if label.lower() == key:
            return slug
    return None
