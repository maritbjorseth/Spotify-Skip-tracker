"""
CLI-inngang for Spotify Skip Tracker.

Bruk:
    python -m spotify_skip_tracker setup --client-id ID --client-secret SECRET
    python -m spotify_skip_tracker run
    python -m spotify_skip_tracker track
    python -m spotify_skip_tracker wrapped [--month 6] [--year 2026]
    python -m spotify_skip_tracker export [--output skips.csv]
"""

import argparse
import logging
import threading


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> None:
    _setup_logging()

    parser = argparse.ArgumentParser(
        prog="python -m spotify_skip_tracker",
        description="Spotify Skip Tracker — se hvilke sanger du skipper, på tvers av enheter.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # setup
    setup_p = sub.add_parser("setup", help="Engangs-innlogging mot Spotify (kjør denne først)")
    setup_p.add_argument("--client-id", required=True, metavar="ID")
    setup_p.add_argument("--client-secret", required=True, metavar="SECRET")

    # run
    sub.add_parser(
        "run",
        help="Start tracking + dashboard på http://localhost:5000",
    )

    # track
    sub.add_parser(
        "track",
        help="Start kun tracking, uten dashboard (for skydeploy, f.eks. Railway)",
    )

    # wrapped
    wrapped_p = sub.add_parser(
        "wrapped",
        help="Generer en personlig 'Wrapped'-rapport som HTML",
    )
    wrapped_p.add_argument(
        "--month", type=int, metavar="1-12",
        help="Filtrer på måned (f.eks. --month 6 for juni)",
    )
    wrapped_p.add_argument(
        "--year", type=int, metavar="ÅÅÅÅ",
        help="Filtrer på år (f.eks. --year 2026)",
    )

    # backfill
    sub.add_parser(
        "backfill",
        help="Fyll inn manglende albumcover for historiske avspillinger",
    )

    # export
    export_p = sub.add_parser(
        "export",
        help="Eksporter alle loggede avspillinger til en CSV-fil",
    )
    export_p.add_argument(
        "--output", default="skips_export.csv", metavar="FIL",
        help="Filnavn/sti for CSV-filen (standard: skips_export.csv)",
    )

    args = parser.parse_args()

    if args.command == "setup":
        from .spotify_api import run_setup
        run_setup(args.client_id, args.client_secret)

    elif args.command == "run":
        import os
        from .database import connect, init_db
        from .tracker import polling_loop
        from .web import create_flask_app

        conn = connect()
        init_db(conn)
        conn.close()

        t = threading.Thread(target=polling_loop, daemon=True)
        t.start()

        port = int(os.environ.get("PORT", 5000))
        app = create_flask_app()
        app.run(host="0.0.0.0", port=port, debug=False)

    elif args.command == "track":
        from .database import connect, init_db
        from .tracker import polling_loop

        conn = connect()
        init_db(conn)
        conn.close()

        polling_loop()

    elif args.command == "wrapped":
        from .wrapped import run_wrapped
        run_wrapped(month=args.month, year=args.year)

    elif args.command == "backfill":
        from .spotify_api import backfill_covers
        backfill_covers()

    elif args.command == "export":
        from .export import run_export
        run_export(args.output)


if __name__ == "__main__":
    main()
