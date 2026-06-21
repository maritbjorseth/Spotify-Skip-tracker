"""
CSV-eksport av alle loggede avspillinger.
"""

import csv
import logging
import sys
from pathlib import Path

from .database import connect, execute

logger = logging.getLogger(__name__)


def run_export(output_path: str | Path) -> None:
    """Eksporterer alle avspillinger til en CSV-fil."""
    output_path = Path(output_path)
    conn = connect()
    try:
        rows = execute(
            conn,
            """
            SELECT
                p.timestamp,
                p.title,
                p.artists,
                p.album,
                COALESCE(c.name, p.context_uri) AS context_name,
                p.skipped,
                p.progress_ratio
            FROM plays p
            LEFT JOIN contexts c ON c.uri = p.context_uri
            ORDER BY p.timestamp
            """,
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        print("Ingen data å eksportere ennå. Kjør 'run' og hør på musikk en stund først.")
        sys.exit(1)

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["timestamp", "title", "artists", "album", "context", "skipped", "progress_ratio"]
        )
        writer.writerows(rows)

    logger.info("Eksporterte %d rader til %s", len(rows), output_path)
    print(f"Eksporterte {len(rows)} rader til {output_path}")
