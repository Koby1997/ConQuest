#!/usr/bin/env python3
"""Start the ConQuest server.

    python run_api.py

Then open http://127.0.0.1:8000 once the frontend has been built
(`npm run build` in frontend/), or run `npm run dev` there for hot reloading
and open http://localhost:5173.
"""

from __future__ import annotations

import argparse

import uvicorn


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="Restart on code changes.")
    args = parser.parse_args()

    uvicorn.run("conquest.api:app", host=args.host, port=args.port, reload=args.reload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
