"""Command line used by the /discover skill (and by hand).

    python -m conquest context [--category maker] [--details]   what to search next, as JSON
    python -m conquest import data/inbox/FILE.json  validate and save a session's findings
    python -m conquest schema                       the import format as JSON Schema
    python -m conquest stats                        what's in the database
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import func, select

from conquest import config
from conquest.categories import CATEGORIES, resolve_category
from conquest.context import build_context
from conquest.db import make_engine, session_scope
from conquest.geo import NominatimGeocoder
from conquest.merge import import_batch
from conquest.models import DiscoveryRun, EventOccurrence, EventSeries
from conquest.schemas import EventBatch, format_validation_error


def _context(args: argparse.Namespace) -> int:
    focus = None
    if args.category:
        focus = resolve_category(args.category)
        if focus is None:
            print(f"Unknown category {args.category!r}. Choose from: {', '.join(CATEGORIES)}", file=sys.stderr)
            return 2

    engine = make_engine()
    with session_scope(engine) as session:
        context = build_context(session, today=date.today(), focus_category=focus, details=args.details)
    print(json.dumps(context, indent=1, ensure_ascii=False))
    return 0


def _import(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if not path.is_file():
        print(f"No such file: {path}", file=sys.stderr)
        return 2

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        print(f"{path.name} is not valid JSON: {error}", file=sys.stderr)
        return 1

    try:
        batch = EventBatch.model_validate(raw)
    except ValidationError as error:
        print(
            f"{path.name} was NOT imported. Fix these {error.error_count()} problem(s) and run import again:\n"
            + format_validation_error(error),
            file=sys.stderr,
        )
        return 1

    engine = make_engine()
    with session_scope(engine) as session:
        geocoder = None if args.no_geocode else NominatimGeocoder(session)
        report = import_batch(session, batch, geocoder=geocoder, file_name=path.name)
    print(report.summary())

    if not args.keep and path.resolve().parent == config.INBOX_DIR.resolve():
        config.IMPORTED_DIR.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), config.IMPORTED_DIR / path.name)
    return 0


def _schema(_: argparse.Namespace) -> int:
    print(json.dumps(EventBatch.model_json_schema(), indent=1))
    return 0


def _stats(_: argparse.Namespace) -> int:
    engine = make_engine()
    with session_scope(engine) as session:
        series = session.scalar(select(func.count()).select_from(EventSeries))
        dates = session.scalar(select(func.count()).select_from(EventOccurrence))
        upcoming = session.scalar(
            select(func.count()).select_from(EventOccurrence).where(EventOccurrence.start_date >= date.today())
        )
        runs = session.scalar(select(func.count()).select_from(DiscoveryRun))
    print(f"Database: {config.DB_PATH}")
    print(f"{series} events, {dates} dates ({upcoming} upcoming), {runs} discovery runs.")
    return 0


def main(argv: list[str] | None = None) -> int:
    # Event names and prices contain characters the Windows console code page
    # can't print (en dashes, accented names).
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(prog="conquest", description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    context = commands.add_parser("context", help="Print what a /discover session needs, as JSON.")
    context.add_argument("--category", help="Focus the suggestion on one category (slug or word like 'maker').")
    context.add_argument(
        "--details", action="store_true", help="Include each known event's description and score (for rescoring)."
    )
    context.set_defaults(handler=_context)

    importer = commands.add_parser("import", help="Validate a findings file and merge it into the database.")
    importer.add_argument("file")
    importer.add_argument("--keep", action="store_true", help="Leave the file in the inbox after importing.")
    importer.add_argument("--no-geocode", action="store_true", help="Skip looking up venue locations.")
    importer.set_defaults(handler=_import)

    schema = commands.add_parser("schema", help="Print the import format as JSON Schema.")
    schema.set_defaults(handler=_schema)

    stats = commands.add_parser("stats", help="Show what's in the database.")
    stats.set_defaults(handler=_stats)

    args = parser.parse_args(argv)
    return args.handler(args)
