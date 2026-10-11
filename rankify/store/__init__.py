"""SQLite storage. No math here.

Source of truth: ``lists``, ``items``, ``judges``, ``queries`` and ``rounds``. Rows are only
ever added; ``items.removed_at`` is the one field set after insert. Everything else
(``fits``, ``fit_items``, ``fit_state``, ``logs``) is derived and can be rebuilt.
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS lists (
    id INTEGER PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    settings TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY,
    list_id INTEGER NOT NULL REFERENCES lists(id),
    name TEXT NOT NULL,
    note TEXT,
    attributes TEXT,
    added_at TEXT NOT NULL,
    removed_at TEXT
) STRICT;
CREATE UNIQUE INDEX IF NOT EXISTS items_active_name
    ON items(list_id, name) WHERE removed_at IS NULL;

CREATE TABLE IF NOT EXISTS judges (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
) STRICT;

-- Every round the planner issued, answered or not.
CREATE TABLE IF NOT EXISTS queries (
    id INTEGER PRIMARY KEY,
    list_id INTEGER NOT NULL REFERENCES lists(id),
    judge_id INTEGER NOT NULL REFERENCES judges(id),
    seq INTEGER NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('pair', 'pick', 'rank')),
    shown TEXT NOT NULL,
    seed INTEGER NOT NULL,
    planner TEXT NOT NULL,
    engine_version TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    UNIQUE (list_id, seq)
) STRICT;

-- The answer log: the source of truth for every fit.
CREATE TABLE IF NOT EXISTS rounds (
    id INTEGER PRIMARY KEY,
    list_id INTEGER NOT NULL REFERENCES lists(id),
    judge_id INTEGER NOT NULL REFERENCES judges(id),
    query_id INTEGER REFERENCES queries(id),
    kind TEXT NOT NULL CHECK (kind IN ('pair', 'pick', 'rank')),
    shown TEXT NOT NULL,
    answer TEXT,
    outcome TEXT NOT NULL CHECK (outcome IN ('answered', 'cant_decide', 'undo')),
    undoes INTEGER REFERENCES rounds(id),
    ms INTEGER,
    seed INTEGER,
    engine_version TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS rounds_list ON rounds(list_id, id);

CREATE TABLE IF NOT EXISTS fits (
    id INTEGER PRIMARY KEY,
    list_id INTEGER NOT NULL REFERENCES lists(id),
    upto_round_id INTEGER,
    n_answers INTEGER NOT NULL,
    engine_version TEXT NOT NULL,
    iterations INTEGER NOT NULL,
    ms REAL NOT NULL,
    params TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX IF NOT EXISTS fits_list ON fits(list_id, id);

CREATE TABLE IF NOT EXISTS fit_items (
    fit_id INTEGER NOT NULL REFERENCES fits(id),
    item_id INTEGER NOT NULL REFERENCES items(id),
    -- NULL where the method has no such notion (Elo has no ranges; a sort has no scores).
    theta REAL,
    sd REAL,
    score REAL,
    rank INTEGER NOT NULL,
    rank_lo INTEGER,
    rank_hi INTEGER,
    confidence REAL,
    PRIMARY KEY (fit_id, item_id)
) STRICT;

-- Latest parameters and covariance per list, for warm starts. Overwritten on each fit.
CREATE TABLE IF NOT EXISTS fit_state (
    list_id INTEGER PRIMARY KEY REFERENCES lists(id),
    fit_id INTEGER NOT NULL REFERENCES fits(id),
    item_ids TEXT NOT NULL,
    x BLOB NOT NULL
) STRICT;

CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    level TEXT NOT NULL,
    event TEXT NOT NULL,
    data TEXT
) STRICT;
"""


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None)  # we manage transactions
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.executescript(_SCHEMA)
    conn.execute(
        "INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    return conn


class Transaction:
    """``with Transaction(conn):`` runs the block in one IMMEDIATE transaction."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def __enter__(self):
        self.conn.execute("BEGIN IMMEDIATE")
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        self.conn.execute("ROLLBACK" if exc_type else "COMMIT")
        return False


# ---------------------------------------------------------------- lists, items, judges


@dataclass(frozen=True)
class ListRow:
    id: int
    slug: str
    title: str
    settings: dict
    created_at: str


@dataclass(frozen=True)
class ItemRow:
    id: int
    name: str
    note: str | None
    removed_at: str | None


def insert_list(conn, slug: str, title: str, settings: dict) -> int:
    cur = conn.execute(
        "INSERT INTO lists(slug, title, settings, created_at) VALUES (?, ?, ?, ?)",
        (slug, title, json.dumps(settings, sort_keys=True), now()),
    )
    return cur.lastrowid


def get_list(conn, slug: str) -> ListRow | None:
    row = conn.execute("SELECT * FROM lists WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        return None
    return ListRow(
        row["id"], row["slug"], row["title"], json.loads(row["settings"]), row["created_at"]
    )


def all_lists(conn) -> list[ListRow]:
    rows = conn.execute("SELECT * FROM lists ORDER BY id").fetchall()
    return [
        ListRow(r["id"], r["slug"], r["title"], json.loads(r["settings"]), r["created_at"])
        for r in rows
    ]


def insert_item(conn, list_id: int, name: str, note: str | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO items(list_id, name, note, added_at) VALUES (?, ?, ?, ?)",
        (list_id, name, note, now()),
    )
    return cur.lastrowid


def items(conn, list_id: int) -> list[ItemRow]:
    """Every item ever added to the list, removed ones included, in insert order."""
    rows = conn.execute(
        "SELECT id, name, note, removed_at FROM items WHERE list_id = ? ORDER BY id", (list_id,)
    ).fetchall()
    return [ItemRow(r["id"], r["name"], r["note"], r["removed_at"]) for r in rows]


def mark_removed(conn, item_id: int) -> None:
    conn.execute(
        "UPDATE items SET removed_at = ? WHERE id = ? AND removed_at IS NULL", (now(), item_id)
    )


def judge_id(conn, name: str) -> int:
    row = conn.execute("SELECT id FROM judges WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    return conn.execute(
        "INSERT INTO judges(name, created_at) VALUES (?, ?)", (name, now())
    ).lastrowid


# ---------------------------------------------------------------- queries and rounds


@dataclass(frozen=True)
class QueryRow:
    id: int
    seq: int
    kind: str
    shown: list[int]
    seed: int
    issued_at: str


@dataclass(frozen=True)
class RoundRow:
    id: int
    judge_id: int
    query_id: int | None
    kind: str
    shown: list[int]
    answer: list[int] | None
    outcome: str
    undoes: int | None
    ms: int | None = None  # time from question to answer


def insert_query(conn, list_id, judge, seq, kind, shown, seed, planner, engine_version) -> QueryRow:
    issued = now()
    qid = conn.execute(
        "INSERT INTO queries(list_id, judge_id, seq, kind, shown, seed, planner, engine_version,"
        " issued_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (list_id, judge, seq, kind, json.dumps(shown), seed, planner, engine_version, issued),
    ).lastrowid
    return QueryRow(qid, seq, kind, list(shown), seed, issued)


def next_seq(conn, list_id: int) -> int:
    row = conn.execute("SELECT MAX(seq) AS s FROM queries WHERE list_id = ?", (list_id,)).fetchone()
    return (row["s"] or 0) + 1


def pending_query(conn, list_id: int, judge: int) -> QueryRow | None:
    """The judge's latest query, if it has no answer yet."""
    row = conn.execute(
        "SELECT q.* FROM queries q WHERE q.list_id = ? AND q.judge_id = ?"
        " AND NOT EXISTS (SELECT 1 FROM rounds r WHERE r.query_id = q.id)"
        " AND q.seq = (SELECT MAX(seq) FROM queries WHERE list_id = ? AND judge_id = ?)",
        (list_id, judge, list_id, judge),
    ).fetchone()
    if row is None:
        return None
    return QueryRow(
        row["id"], row["seq"], row["kind"], json.loads(row["shown"]), row["seed"], row["issued_at"]
    )


def insert_round(
    conn,
    list_id,
    judge,
    *,
    query_id,
    kind,
    shown,
    answer,
    outcome,
    undoes,
    ms,
    seed,
    engine_version,
) -> int:
    return conn.execute(
        "INSERT INTO rounds(list_id, judge_id, query_id, kind, shown, answer, outcome, undoes, ms,"
        " seed, engine_version, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            list_id,
            judge,
            query_id,
            kind,
            json.dumps(shown),
            None if answer is None else json.dumps(answer),
            outcome,
            undoes,
            ms,
            seed,
            engine_version,
            now(),
        ),
    ).lastrowid


def effective_rounds(conn, list_id: int) -> list[RoundRow]:
    """Answered and can't-decide rounds that no undo has cancelled, oldest first."""
    rows = conn.execute(
        "SELECT * FROM rounds r WHERE r.list_id = ? AND r.outcome IN ('answered', 'cant_decide')"
        " AND NOT EXISTS (SELECT 1 FROM rounds u WHERE u.outcome = 'undo' AND u.undoes = r.id)"
        " ORDER BY r.id",
        (list_id,),
    ).fetchall()
    return [
        RoundRow(
            r["id"],
            r["judge_id"],
            r["query_id"],
            r["kind"],
            json.loads(r["shown"]),
            None if r["answer"] is None else json.loads(r["answer"]),
            r["outcome"],
            r["undoes"],
            r["ms"],
        )
        for r in rows
    ]


def last_round_id(conn, list_id: int) -> int | None:
    row = conn.execute("SELECT MAX(id) AS m FROM rounds WHERE list_id = ?", (list_id,)).fetchone()
    return row["m"]


def query_by_id(conn, query_id: int) -> QueryRow | None:
    row = conn.execute("SELECT * FROM queries WHERE id = ?", (query_id,)).fetchone()
    if row is None:
        return None
    return QueryRow(
        row["id"], row["seq"], row["kind"], json.loads(row["shown"]), row["seed"], row["issued_at"]
    )


# ---------------------------------------------------------------- derived: fits


@dataclass(frozen=True)
class FitItemRow:
    item_id: int
    theta: float | None
    sd: float | None
    score: float | None
    rank: int
    rank_lo: int | None
    rank_hi: int | None
    confidence: float | None


@dataclass(frozen=True)
class FitRow:
    id: int
    upto_round_id: int | None
    n_answers: int
    engine_version: str
    iterations: int
    ms: float
    params: dict
    items: list[FitItemRow]


def insert_fit(
    conn,
    list_id,
    *,
    upto_round_id,
    n_answers,
    engine_version,
    iterations,
    ms,
    params,
    item_rows: list[FitItemRow],
    item_ids: list[int],
    x_bytes: bytes | None,
) -> int:
    """Store a fit. ``x_bytes`` is the warm-start state; None for methods without one."""
    fit_id = conn.execute(
        "INSERT INTO fits(list_id, upto_round_id, n_answers, engine_version, iterations, ms, params,"
        " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            list_id,
            upto_round_id,
            n_answers,
            engine_version,
            iterations,
            ms,
            json.dumps(params, sort_keys=True),
            now(),
        ),
    ).lastrowid
    conn.executemany(
        "INSERT INTO fit_items(fit_id, item_id, theta, sd, score, rank, rank_lo, rank_hi, confidence)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (fit_id, r.item_id, r.theta, r.sd, r.score, r.rank, r.rank_lo, r.rank_hi, r.confidence)
            for r in item_rows
        ],
    )
    if x_bytes is not None:
        conn.execute(
            "INSERT INTO fit_state(list_id, fit_id, item_ids, x) VALUES (?, ?, ?, ?)"
            " ON CONFLICT(list_id) DO UPDATE SET fit_id = excluded.fit_id,"
            " item_ids = excluded.item_ids, x = excluded.x",
            (list_id, fit_id, json.dumps(item_ids), x_bytes),
        )
    return fit_id


def latest_fit(conn, list_id: int) -> FitRow | None:
    row = conn.execute(
        "SELECT * FROM fits WHERE list_id = ? ORDER BY id DESC LIMIT 1", (list_id,)
    ).fetchone()
    if row is None:
        return None
    rows = conn.execute(
        "SELECT * FROM fit_items WHERE fit_id = ? ORDER BY rank", (row["id"],)
    ).fetchall()
    return FitRow(
        row["id"],
        row["upto_round_id"],
        row["n_answers"],
        row["engine_version"],
        row["iterations"],
        row["ms"],
        json.loads(row["params"]),
        [
            FitItemRow(
                r["item_id"],
                r["theta"],
                r["sd"],
                r["score"],
                r["rank"],
                r["rank_lo"],
                r["rank_hi"],
                r["confidence"],
            )
            for r in rows
        ],
    )


def fit_state(conn, list_id: int) -> tuple[list[int], bytes] | None:
    row = conn.execute("SELECT item_ids, x FROM fit_state WHERE list_id = ?", (list_id,)).fetchone()
    if row is None:
        return None
    return json.loads(row["item_ids"]), row["x"]


def log(conn, level: str, event: str, data: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO logs(ts, level, event, data) VALUES (?, ?, ?, ?)",
        (now(), level, event, None if data is None else json.dumps(data, sort_keys=True)),
    )
