"""Move the root user's holdings and history into a private account.

Root becomes a read-only combined view of every account, so anything root
owns directly has to live in a real account to keep counting in the total.

Usage (from backend/):
    python scripts/merge_root_into_account.py --to Mastermind --dry-run
    python scripts/merge_root_into_account.py --to Mastermind

Stop the backend first so no snapshot is written mid-merge. A timestamped
backup of the database is written next to it before any change.
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime

DEFAULT_DB = os.path.join(os.path.dirname(__file__), "..", "instance", "portfolio.db")
VALUE_COLUMNS = ("total_value", "stock_value", "property_equity", "options_value")


def backup(db_path):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(os.path.dirname(db_path), f"portfolio.backup-{stamp}.db")
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(dest)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    return dest


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--to", default="Mastermind", help="username of the account that receives root's data")
    parser.add_argument("--db", default=DEFAULT_DB, help="path to portfolio.db")
    parser.add_argument("--dry-run", action="store_true", help="show what would change without writing")
    args = parser.parse_args()

    db_path = os.path.abspath(args.db)
    if not os.path.exists(db_path):
        sys.exit(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    root = cur.execute("SELECT id, username FROM users WHERE role = 'root'").fetchone()
    if not root:
        sys.exit("No root user found.")
    target = cur.execute(
        "SELECT id, username, role FROM users WHERE username = ?", (args.to,)
    ).fetchone()
    if not target:
        sys.exit(f"Account {args.to!r} not found.")
    if target[2] == "root":
        sys.exit("Target must be a private account, not root.")
    root_id, target_id = root[0], target[0]

    counts = {
        t: cur.execute(f"SELECT COUNT(*) FROM {t} WHERE owner_id = ?", (root_id,)).fetchone()[0]
        for t in ("stocks", "options", "properties")
    }
    snap_total = cur.execute(
        "SELECT COUNT(*) FROM portfolio_snapshots WHERE owner_id = ?", (root_id,)
    ).fetchone()[0]
    snap_matched = cur.execute(
        """SELECT COUNT(*) FROM portfolio_snapshots r
           WHERE r.owner_id = ? AND EXISTS (
               SELECT 1 FROM portfolio_snapshots t
               WHERE t.owner_id = ? AND t.timestamp = r.timestamp)""",
        (root_id, target_id),
    ).fetchone()[0]

    print(f"Moving root's data into {target[1]!r} (id {target_id}) in {db_path}")
    for table, n in counts.items():
        print(f"  {table}: {n} row(s) reassigned")
    print(f"  snapshots: {snap_matched} merged into matching timestamps, "
          f"{snap_total - snap_matched} reassigned")

    if not any(counts.values()) and not snap_total:
        print("Root owns nothing; nothing to do.")
        return
    if args.dry_run:
        print("Dry run: no changes written.")
        return

    print(f"Backup written to {backup(db_path)}")

    with conn:
        for table in counts:
            cur.execute(f"UPDATE {table} SET owner_id = ? WHERE owner_id = ?", (target_id, root_id))

        sums = ", ".join(
            f"""{c} = COALESCE({c}, 0) + COALESCE((
                    SELECT r.{c} FROM portfolio_snapshots r
                    WHERE r.owner_id = :root AND r.timestamp = portfolio_snapshots.timestamp), 0)"""
            for c in VALUE_COLUMNS
        )
        cur.execute(
            f"""UPDATE portfolio_snapshots SET {sums}
                WHERE owner_id = :target AND timestamp IN (
                    SELECT timestamp FROM portfolio_snapshots WHERE owner_id = :root)""",
            {"root": root_id, "target": target_id},
        )
        cur.execute(
            """DELETE FROM portfolio_snapshots
               WHERE owner_id = :root AND timestamp IN (
                   SELECT timestamp FROM portfolio_snapshots WHERE owner_id = :target)""",
            {"root": root_id, "target": target_id},
        )
        cur.execute(
            "UPDATE portfolio_snapshots SET owner_id = ? WHERE owner_id = ?", (target_id, root_id)
        )

    print("Done.")


if __name__ == "__main__":
    main()
