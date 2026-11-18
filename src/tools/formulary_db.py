from __future__ import annotations

import csv
import math
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from src.config import settings

BASE_DIR = Path(__file__).resolve().parent.parent.parent

REQUIRED_COLUMNS: list[str] = [
    "record_id",
    "drug_name",
    "generic_name",
    "brand_name",
    "plan_id",
    "plan_name",
    "tier",
    "copay",
    "coverage_status",
    "requires_pa",
    "pa_criteria",
    "requires_step_therapy",
    "step_therapy_alternatives",
    "quantity_limit",
    "data_source",
]

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS formulary (
    record_id TEXT PRIMARY KEY,
    drug_name TEXT NOT NULL,
    generic_name TEXT NOT NULL,
    brand_name TEXT,
    plan_id TEXT NOT NULL,
    plan_name TEXT NOT NULL,
    tier INTEGER NOT NULL,
    copay REAL NOT NULL,
    coverage_status TEXT NOT NULL,
    requires_pa INTEGER NOT NULL,
    pa_criteria TEXT,
    requires_step_therapy INTEGER NOT NULL,
    step_therapy_alternatives TEXT,
    quantity_limit TEXT,
    data_source TEXT NOT NULL
)
"""

_INDEX_SQL: list[str] = [
    "CREATE INDEX IF NOT EXISTS idx_formulary_generic_name ON formulary (generic_name)",
    "CREATE INDEX IF NOT EXISTS idx_formulary_drug_name ON formulary (drug_name)",
    "CREATE INDEX IF NOT EXISTS idx_formulary_plan_id ON formulary (plan_id)",
]

_UPSERT_SQL = f"""
INSERT INTO formulary ({", ".join(REQUIRED_COLUMNS)})
VALUES ({", ".join(":" + column for column in REQUIRED_COLUMNS)})
ON CONFLICT(record_id) DO UPDATE SET
    {", ".join(f"{c} = excluded.{c}" for c in REQUIRED_COLUMNS if c != "record_id")}
"""

_NOT_NULL_TEXT_COLUMNS: list[str] = [
    "record_id",
    "drug_name",
    "generic_name",
    "plan_id",
    "plan_name",
    "coverage_status",
    "data_source",
]

_OPTIONAL_TEXT_COLUMNS: tuple[str, ...] = (
    "brand_name",
    "pa_criteria",
    "step_therapy_alternatives",
    "quantity_limit",
)


def _resolve_database_path(database_url: str) -> Path:
    """Convert a ``sqlite:///`` URL into an absolute path.

    Relative paths are resolved against the project root, not the current
    working directory.
    """
    parsed = urlparse(database_url)
    if parsed.scheme != "sqlite":
        raise ValueError(
            f"Unsupported database URL scheme '{parsed.scheme}'; expected 'sqlite'."
        )
    # "sqlite:///./data/x.db" -> path "/./data/x.db"; "sqlite:////abs/x.db" -> "//abs/x.db"
    raw_path = unquote(parsed.path)
    if raw_path.startswith("//"):
        path = Path(raw_path[1:])  # absolute POSIX path
    else:
        raw_path = raw_path[1:] if raw_path.startswith("/") else raw_path
        if not raw_path or raw_path == ":memory:":
            raise ValueError("A file-based SQLite database path is required.")
        path = Path(raw_path)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


def _parse_bool(value: str, field: str, row_number: int) -> int:
    """Convert 'true'/'false' (case-insensitive) to 1/0."""
    normalized = value.strip().lower()
    if normalized == "true":
        return 1
    if normalized == "false":
        return 0
    raise ValueError(
        f"Row {row_number}: '{field}' must be 'true' or 'false', got {value!r}."
    )


class FormularyDatabase:
    """SQLite-backed store for synthetic formulary records."""

    def __init__(self, database_url: str | None = None) -> None:
        """Resolve the database path, create its directory, and initialize the schema."""
        self.db_path: Path = _resolve_database_path(
            database_url if database_url is not None else settings.database_url
        )
        self._connection: sqlite3.Connection | None = None
        self.initialize()

    def get_connection(self) -> sqlite3.Connection:
        """Return the persistent connection, opening it if needed."""
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_path)
            self._connection.row_factory = sqlite3.Row
        return self._connection

    def initialize(self) -> None:
        """Create the parent directory, the ``formulary`` table, and its indexes."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = self.get_connection()
        with connection:
            connection.execute(_CREATE_TABLE_SQL)
            for statement in _INDEX_SQL:
                connection.execute(statement)

    def load_csv(self, csv_path: str | Path) -> int:
        """Load formulary records from a CSV file using upserts.

        The import is atomic: if any row is invalid, nothing is written.

        Args:
            csv_path: Path to the formulary CSV.

        Returns:
            The number of records processed.

        Raises:
            FileNotFoundError: If the CSV file does not exist.
            ValueError: If required columns are missing or a row is invalid.
        """
        path = Path(csv_path)
        if not path.is_file():
            raise FileNotFoundError(f"CSV file not found: {path}")

        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            fieldnames = reader.fieldnames or []
            missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
            if missing:
                raise ValueError(f"CSV is missing required columns: {', '.join(missing)}")

            for row_number, row in enumerate(reader, start=2):
                rows.append(self._convert_row(row, row_number))

        connection = self.get_connection()
        with connection:
            connection.executemany(_UPSERT_SQL, rows)
        return len(rows)

    @staticmethod
    def _convert_row(row: dict[str, str | None], row_number: int) -> dict[str, Any]:
        """Validate and convert one CSV row to database types."""
        values = {column: (row.get(column) or "").strip() for column in REQUIRED_COLUMNS}

        for column in _NOT_NULL_TEXT_COLUMNS:
            if not values[column]:
                raise ValueError(f"Row {row_number}: '{column}' must not be empty.")

        try:
            tier = int(values["tier"])
        except ValueError as exc:
            raise ValueError(
                f"Row {row_number}: 'tier' must be an integer, got {values['tier']!r}."
            ) from exc

        try:
            copay = float(values["copay"])
        except ValueError as exc:
            raise ValueError(
                f"Row {row_number}: 'copay' must be a number, got {values['copay']!r}."
            ) from exc
        if not math.isfinite(copay) or copay < 0:
            raise ValueError(
                f"Row {row_number}: 'copay' must be a finite, non-negative number, "
                f"got {values['copay']!r}."
            )

        converted: dict[str, Any] = dict(values)
        converted["tier"] = tier
        converted["copay"] = copay
        converted["requires_pa"] = _parse_bool(values["requires_pa"], "requires_pa", row_number)
        converted["requires_step_therapy"] = _parse_bool(
            values["requires_step_therapy"], "requires_step_therapy", row_number
        )
        # Optional text fields are stored as NULL when empty.
        for column in _OPTIONAL_TEXT_COLUMNS:
            converted[column] = values[column] or None
        return converted

    def get_record_count(self) -> int:
        """Return the number of records in the ``formulary`` table."""
        row = self.get_connection().execute("SELECT COUNT(*) FROM formulary").fetchone()
        return int(row[0])

    def close(self) -> None:
        """Close the persistent connection, if open."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> FormularyDatabase:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()