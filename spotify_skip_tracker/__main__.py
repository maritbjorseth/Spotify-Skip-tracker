"""
CLI-inngang for Spotify Skip Tracker.

Bruk:
    python -m spotify_skip_tracker setup --client-id ID --client-secret SECRET
    python -m spotify_skip_tracker run
    python -m spotify_skip_tracker track
    python -m spotify_skip_tracker wrapped [--month 6] [--year 2026]
    python -m spotify_skip_tracker export [--output skips.csv]
    python -m spotify_skip_tracker smart-skipper status
    python -m spotify_skip_tracker janitor [--playlist NAVN] [--min-score 0.70] [--no-dry-run]
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

    # smart-skipper
    ss_p = sub.add_parser(
        "smart-skipper",
        help="Administrer Smart Skipper-innstillinger",
    )
    ss_p.add_argument(
        "action",
        choices=["status", "enable", "disable", "dry-run", "threshold"],
        help="Handling som skal utføres",
    )
    ss_p.add_argument(
        "value",
        nargs="?",
        default=None,
        metavar="VERDI",
        help="Verdi for 'dry-run' (on/off) eller 'threshold' (0.50–1.00)",
    )
    ss_p.set_defaults(func=handle_smart_skipper)

    # janitor
    janitor_p = sub.add_parser(
        "janitor",
        help="Analyser spillelister og finn kandidater for fjerning (Playlist Janitor)",
    )
    janitor_p.add_argument(
        "--playlist",
        type=str,
        default=None,
        metavar="NAVN",
        help="Filtrer på spillelistenavn (case-insensitiv delstreng)",
    )
    janitor_p.add_argument(
        "--min-score",
        type=float,
        default=0.70,
        metavar="SCORE",
        help="Minimum janitor-score for å inkludere en kandidat (standard: 0.70)",
    )
    janitor_p.add_argument(
        "--min-plays",
        type=int,
        default=3,
        metavar="N",
        help="Minimum antall avspillinger i spillelisten (standard: 3)",
    )
    janitor_p.add_argument(
        "--no-dry-run",
        action="store_true",
        help="Deaktiver dry-run og lagre forslag til databasen (standard: dry-run aktiv)",
    )
    janitor_p.set_defaults(func=handle_janitor)

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

    elif args.command == "smart-skipper":
        handle_smart_skipper(args)

    elif args.command == "janitor":
        handle_janitor(args)


def handle_smart_skipper(args) -> None:
    from .database import (
        connect, execute, init_db,
        _detect_owner_user_id, ensure_user_smart_skipper_config,
    )

    conn = connect()
    init_db(conn)

    # Finn eierens user_id — CLIen opererer alltid på eierens konto
    user_id = _detect_owner_user_id(conn) or "default_user"
    ensure_user_smart_skipper_config(conn, user_id)

    if args.action == "status":
        row = execute(
            conn,
            """
            SELECT enabled, threshold, min_plays, dry_run
            FROM smart_skipper_config
            WHERE user_id = %s
            """,
            (user_id,),
        ).fetchone()
        if not row:
            print("Ingen konfigurasjon funnet — kjør init_db først.")
        else:
            enabled, threshold, min_plays, dry_run = row
            print(f"Smart Skipper: {'PÅ' if enabled else 'AV'}")
            print(f"  Bruker:      {user_id}")
            print(f"  Terskel:     {threshold:.0%}")
            print(f"  Min avspill: {min_plays}")
            print(f"  Prøvemodus:  {'JA' if dry_run else 'NEI'}")

    elif args.action == "enable":
        execute(
            conn,
            "UPDATE smart_skipper_config SET enabled = TRUE WHERE user_id = %s",
            (user_id,),
        )
        conn.commit()
        print("Smart Skipper aktivert.")

    elif args.action == "disable":
        execute(
            conn,
            "UPDATE smart_skipper_config SET enabled = FALSE WHERE user_id = %s",
            (user_id,),
        )
        conn.commit()
        print("Smart Skipper deaktivert.")

    elif args.action == "dry-run":
        if args.value is None:
            print("Feil: oppgi verdi — 'on' eller 'off'.")
        else:
            val = args.value.lower() in ("on", "true", "1", "ja")
            execute(
                conn,
                "UPDATE smart_skipper_config SET dry_run = %s WHERE user_id = %s",
                (val, user_id),
            )
            conn.commit()
            print(f"Prøvemodus: {'PÅ' if val else 'AV'}")

    elif args.action == "threshold":
        if args.value is None:
            print("Feil: oppgi en verdi mellom 0.50 og 1.00.")
        else:
            try:
                t = float(args.value)
            except ValueError:
                print(f"Feil: '{args.value}' er ikke et gyldig tall.")
                conn.close()
                return
            if not 0.50 <= t <= 1.00:
                print("Feil: terskel må være mellom 0.50 og 1.00.")
            else:
                execute(
                    conn,
                    "UPDATE smart_skipper_config SET threshold = %s WHERE user_id = %s",
                    (t, user_id),
                )
                conn.commit()
                print(f"Terskel satt til {t:.0%}")

    conn.close()


def handle_janitor(args) -> None:
    from .janitor import run_janitor

    dry_run = not args.no_dry_run

    print(
        f"Playlist Janitor starter"
        f"{' [DRY RUN — ingen DB-skriving]' if dry_run else ' [AKTIV — lagrer forslag]'}"
    )
    if args.playlist:
        print(f"  Filter:      '{args.playlist}'")
    print(f"  Min score:   {args.min_score:.0%}")
    print(f"  Min avspill: {args.min_plays}")
    print()

    result = run_janitor(
        playlist_filter=args.playlist,
        min_score=float(args.min_score),
        min_plays=int(args.min_plays),
        dry_run=dry_run,
    )

    analysed = result["playlists_analysed"]
    skipped = result["playlists_skipped"]
    total = result["total_candidates"]

    print(f"Analyserte spillelister: {analysed}")
    if skipped:
        print(f"Hoppet over (ingen spor/data): {skipped}")
    print(f"Totalt antall kandidater funnet: {total}")
    print()

    for entry in result["results"]:
        candidates = entry["candidates"]
        if not candidates:
            continue
        print(f"  {entry['playlist_name']} — {len(candidates)} kandidat(er):")
        for c in candidates:
            print(
                f"    [{c['score']:.2f}] {c['artists']} — {c['title']}"
                f"  (skip {c['skip_count']}/{c['play_count']}, "
                f"rate {c['skip_rate']:.0%})"
            )
        print()

    if total == 0:
        print("Ingen kandidater funnet over terskelen.")
    elif dry_run:
        print(
            "Dry-run aktiv — ingen endringer lagret. "
            "Bruk --no-dry-run for å lagre forslagene til databasen."
        )
    else:
        print(f"{total} forslag lagret i janitor_suggestions-tabellen.")


if __name__ == "__main__":
    main()
