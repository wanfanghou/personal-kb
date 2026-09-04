"""Export verified public lineage data from the local SQLite database."""
import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.exporter import export_public_data  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=str(ROOT / "data" / "network.sqlite"))
    parser.add_argument("--output", default=str(ROOT / "public" / "data"))
    args = parser.parse_args()

    database = Path(args.database)
    if not database.exists():
        print(f"error: database not found: {database}")
        return 1

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        result = export_public_data(connection, args.output)
    finally:
        connection.close()
    print(
        f"exported {result['people']} people and {result['relationships']} relationships "
        f"to {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
