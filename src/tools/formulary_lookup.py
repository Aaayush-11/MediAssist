from __future__ import annotations

from typing import Any

from rapidfuzz import fuzz

from src.tools.formulary_db import FormularyDatabase

# Minimum fuzz.ratio score (0-100) for an approximate match.
FUZZY_THRESHOLD: float = 80.0
# Minimum score lead the best fuzzy candidate needs over the runner-up
# for the match to be treated as unambiguous.
FUZZY_AMBIGUITY_MARGIN: float = 5.0

_RECORD_COLUMNS = (
    "record_id, drug_name, generic_name, brand_name, plan_id, plan_name, "
    "tier, copay, coverage_status, requires_pa, pa_criteria, "
    "requires_step_therapy, step_therapy_alternatives, quantity_limit, data_source"
)


def _escape_like(value: str) -> str:
    """Escape LIKE wildcards so user input is matched literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class FormularyLookup:
    """Structured, parameterized lookups against the formulary database."""

    def __init__(self, database: FormularyDatabase | None = None) -> None:
        """Use the supplied database, or create a default one internally."""
        self._owns_database: bool = database is None
        self._database: FormularyDatabase = (
            database if database is not None else FormularyDatabase()
        )

    @staticmethod
    def _validate_inputs(query: Any, plan_id: Any) -> tuple[str, str | None]:
        """Validate and normalize query and plan_id."""
        if not isinstance(query, str):
            raise TypeError(f"query must be a string, got {type(query).__name__}.")
        cleaned_query = query.strip()
        if not cleaned_query:
            raise ValueError("query must not be empty or whitespace-only.")

        cleaned_plan: str | None = None
        if plan_id is not None:
            if not isinstance(plan_id, str):
                raise TypeError(f"plan_id must be a string or None, got {type(plan_id).__name__}.")
            cleaned_plan = plan_id.strip()
            if not cleaned_plan:
                raise ValueError("plan_id must not be empty or whitespace-only.")
        return cleaned_query, cleaned_plan

    @staticmethod
    def _row_to_dict(row: Any) -> dict[str, Any]:
        """Convert a database row to a result dictionary."""
        return {
            "record_id": row["record_id"],
            "drug_name": row["drug_name"],
            "generic_name": row["generic_name"],
            "brand_name": row["brand_name"],
            "plan_id": row["plan_id"],
            "plan_name": row["plan_name"],
            "tier": row["tier"],
            "copay": row["copay"],
            "coverage_status": row["coverage_status"],
            "requires_pa": bool(row["requires_pa"]),
            "pa_criteria": row["pa_criteria"],
            "requires_step_therapy": bool(row["requires_step_therapy"]),
            "step_therapy_alternatives": row["step_therapy_alternatives"],
            "quantity_limit": row["quantity_limit"],
            "data_source": row["data_source"],
        }

    def _exact_records(self, query: str, plan_id: str | None) -> list[dict[str, Any]]:
        """Case-insensitive substring match on generic_name and drug_name."""
        pattern = f"%{_escape_like(query.lower())}%"
        sql = (
            f"SELECT {_RECORD_COLUMNS} FROM formulary "
            "WHERE (LOWER(generic_name) LIKE :pattern ESCAPE '\\' "
            "OR LOWER(drug_name) LIKE :pattern ESCAPE '\\')"
        )
        params: dict[str, Any] = {"pattern": pattern}
        if plan_id is not None:
            sql += " AND UPPER(plan_id) = UPPER(:plan_id)"
            params["plan_id"] = plan_id
        sql += " ORDER BY generic_name, plan_id"
        rows = self._database.get_connection().execute(sql, params).fetchall()
        return self._dedupe([self._row_to_dict(row) for row in rows])

    def _fuzzy_generics(self, query: str, plan_id: str | None) -> list[tuple[str, float]]:
        """Return (generic_name, score) pairs above the threshold, best first."""
        sql = "SELECT DISTINCT generic_name, brand_name, drug_name FROM formulary"
        params: dict[str, Any] = {}
        if plan_id is not None:
            sql += " WHERE UPPER(plan_id) = UPPER(:plan_id)"
            params["plan_id"] = plan_id
        rows = self._database.get_connection().execute(sql, params).fetchall()

        lowered = query.lower()
        scored: dict[str, float] = {}
        for row in rows:
            generic: str = row["generic_name"]
            names = [generic.lower()]
            if row["brand_name"]:
                names.append(row["brand_name"].lower())
            if row["drug_name"]:
                names.append(row["drug_name"].lower())
            score = max(fuzz.ratio(lowered, name) for name in names)
            if score >= FUZZY_THRESHOLD:
                scored[generic] = max(score, scored.get(generic, 0.0))
        return sorted(scored.items(), key=lambda item: (-item[1], item[0]))

    def _records_for_generics(
        self, generics: list[str], plan_id: str | None
    ) -> list[dict[str, Any]]:
        """Fetch records for the given generic names."""
        if not generics:
            return []
        placeholders = ", ".join(f":g{i}" for i in range(len(generics)))
        params: dict[str, Any] = {f"g{i}": name for i, name in enumerate(generics)}
        sql = f"SELECT {_RECORD_COLUMNS} FROM formulary WHERE generic_name IN ({placeholders})"
        if plan_id is not None:
            sql += " AND UPPER(plan_id) = UPPER(:plan_id)"
            params["plan_id"] = plan_id
        sql += " ORDER BY generic_name, plan_id"
        rows = self._database.get_connection().execute(sql, params).fetchall()
        return self._dedupe([self._row_to_dict(row) for row in rows])

    @staticmethod
    def _dedupe(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Remove duplicate records by record_id, preserving order."""
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for record in records:
            if record["record_id"] not in seen:
                seen.add(record["record_id"])
                unique.append(record)
        return unique

    def search_medication(self, query: str, plan_id: str | None = None) -> list[dict[str, Any]]:
        """Search medications by generic or drug name, optionally filtered by plan.

        Substring matching is tried first (case-insensitive). If it finds
        nothing, RapidFuzz approximate matching is used with a similarity
        threshold so unrelated medications are not returned.

        Raises:
            TypeError: If query or plan_id has the wrong type.
            ValueError: If query or plan_id is blank.
        """
        cleaned_query, cleaned_plan = self._validate_inputs(query, plan_id)
        records = self._exact_records(cleaned_query, cleaned_plan)
        if records:
            return records
        fuzzy = self._fuzzy_generics(cleaned_query, cleaned_plan)
        return self._records_for_generics([name for name, _ in fuzzy], cleaned_plan)

    def get_medication_details(self, query: str, plan_id: str | None = None) -> dict[str, Any]:
        """Return formulary details for a single medication.

        Returns a dict whose ``status`` is one of:
            ``found``: includes ``generic_name``, ``drug_name``, ``brand_name``
                and ``records`` (one per matching plan).
            ``not_found``: includes a ``message``.
            ``ambiguous``: includes ``candidates`` and a ``message``.
        """
        cleaned_query, cleaned_plan = self._validate_inputs(query, plan_id)
        records = self._exact_records(cleaned_query, cleaned_plan)

        if not records:
            fuzzy = self._fuzzy_generics(cleaned_query, cleaned_plan)
            if not fuzzy:
                return {
                    "status": "not_found",
                    "query": cleaned_query,
                    "plan_id": cleaned_plan,
                    "message": f"No medication matching '{cleaned_query}' was found.",
                }
            if len(fuzzy) > 1 and fuzzy[0][1] - fuzzy[1][1] < FUZZY_AMBIGUITY_MARGIN:
                records = self._records_for_generics([name for name, _ in fuzzy], cleaned_plan)
            else:
                records = self._records_for_generics([fuzzy[0][0]], cleaned_plan)

        generics = sorted({record["generic_name"] for record in records})
        if len(generics) > 1:
            lowered = cleaned_query.lower()
            exact_generics = sorted(
                {
                    r["generic_name"]
                    for r in records
                    if lowered
                    in {
                        r["generic_name"].lower(),
                        r["drug_name"].lower(),
                        (r["brand_name"] or "").lower(),
                    }
                }
            )
            if len(exact_generics) == 1:
                generics = exact_generics
                records = [r for r in records if r["generic_name"] == exact_generics[0]]

        if len(generics) > 1:
            candidates: list[dict[str, Any]] = []
            seen: set[str] = set()
            for record in records:
                if record["generic_name"] not in seen:
                    seen.add(record["generic_name"])
                    candidates.append(
                        {
                            "drug_name": record["drug_name"],
                            "generic_name": record["generic_name"],
                            "brand_name": record["brand_name"],
                        }
                    )
            return {
                "status": "ambiguous",
                "query": cleaned_query,
                "plan_id": cleaned_plan,
                "candidates": candidates,
                "message": (
                    f"'{cleaned_query}' matches multiple medications; "
                    "please specify which one is meant."
                ),
            }

        first = records[0]
        return {
            "status": "found",
            "query": cleaned_query,
            "plan_id": cleaned_plan,
            "drug_name": first["drug_name"],
            "generic_name": first["generic_name"],
            "brand_name": first["brand_name"],
            "records": records,
        }

    def close(self) -> None:
        """Close the database if it was created by this instance."""
        if self._owns_database:
            self._database.close()

    def __enter__(self) -> FormularyLookup:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()