from __future__ import annotations

import csv
import random
from pathlib import Path
from typing import Any

SEED = 20260101
DATA_SOURCE = "SYNTHETIC_DEMO_DATA"

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "raw" / "formulary.csv"

PLANS: list[tuple[str, str]] = [
    ("PLAN_BASIC", "MediAssist Basic"),
    ("PLAN_PLUS", "MediAssist Plus"),
    ("PLAN_PREMIUM", "MediAssist Premium"),
]

# (generic_name, brand_name). Brand name is empty when the drug is commonly generic-only.
MEDICATIONS: list[tuple[str, str]] = [
    ("metformin", "Glucophage"),
    ("lisinopril", "Zestril"),
    ("atorvastatin", "Lipitor"),
    ("amlodipine", "Norvasc"),
    ("metoprolol succinate", "Toprol-XL"),
    ("omeprazole", "Prilosec"),
    ("losartan", "Cozaar"),
    ("albuterol", "Ventolin HFA"),
    ("gabapentin", "Neurontin"),
    ("sertraline", "Zoloft"),
    ("levothyroxine", "Synthroid"),
    ("simvastatin", "Zocor"),
    ("hydrochlorothiazide", ""),
    ("furosemide", "Lasix"),
    ("pantoprazole", "Protonix"),
    ("escitalopram", "Lexapro"),
    ("bupropion", "Wellbutrin XL"),
    ("fluoxetine", "Prozac"),
    ("montelukast", "Singulair"),
    ("rosuvastatin", "Crestor"),
    ("carvedilol", "Coreg"),
    ("tamsulosin", "Flomax"),
    ("prednisone", "Deltasone"),
    ("trazodone", "Desyrel"),
    ("clopidogrel", "Plavix"),
    ("warfarin", "Coumadin"),
    ("apixaban", "Eliquis"),
    ("rivaroxaban", "Xarelto"),
    ("dabigatran", "Pradaxa"),
    ("insulin glargine", "Lantus"),
    ("insulin lispro", "Humalog"),
    ("insulin aspart", "Novolog"),
    ("semaglutide", "Ozempic"),
    ("liraglutide", "Victoza"),
    ("dulaglutide", "Trulicity"),
    ("empagliflozin", "Jardiance"),
    ("dapagliflozin", "Farxiga"),
    ("canagliflozin", "Invokana"),
    ("sitagliptin", "Januvia"),
    ("linagliptin", "Tradjenta"),
    ("glipizide", "Glucotrol"),
    ("pioglitazone", "Actos"),
    ("sacubitril/valsartan", "Entresto"),
    ("ticagrelor", "Brilinta"),
    ("ezetimibe", "Zetia"),
    ("evolocumab", "Repatha"),
    ("adalimumab", "Humira"),
    ("etanercept", "Enbrel"),
    ("ustekinumab", "Stelara"),
    ("secukinumab", "Cosentyx"),
    ("tofacitinib", "Xeljanz"),
    ("upadacitinib", "Rinvoq"),
    ("methotrexate", "Trexall"),
    ("hydroxychloroquine", "Plaquenil"),
    ("dupilumab", "Dupixent"),
    ("omalizumab", "Xolair"),
    ("fluticasone/salmeterol", "Advair Diskus"),
    ("budesonide/formoterol", "Symbicort"),
    ("tiotropium", "Spiriva"),
    ("sumatriptan", "Imitrex"),
    ("rizatriptan", "Maxalt"),
    ("erenumab", "Aimovig"),
    ("levetiracetam", "Keppra"),
    ("lamotrigine", "Lamictal"),
    ("topiramate", "Topamax"),
    ("aripiprazole", "Abilify"),
    ("quetiapine", "Seroquel"),
    ("lurasidone", "Latuda"),
    ("duloxetine", "Cymbalta"),
    ("venlafaxine", "Effexor XR"),
    ("methylphenidate", "Concerta"),
    ("lisdexamfetamine", "Vyvanse"),
    ("oxycodone", "OxyContin"),
    ("celecoxib", "Celebrex"),
    ("meloxicam", "Mobic"),
    ("cyclobenzaprine", "Flexeril"),
    ("ondansetron", "Zofran"),
    ("famotidine", "Pepcid"),
    ("mesalamine", "Lialda"),
    ("ledipasvir/sofosbuvir", "Harvoni"),
]

PA_CRITERIA: list[str] = [
    "SYNTHETIC RULE: Demonstration criteria require documented diagnosis code on file.",
    "SYNTHETIC RULE: Demonstration criteria require documented trial of a first-line agent.",
    "SYNTHETIC RULE: Demonstration criteria require specialist consultation note.",
    "SYNTHETIC RULE: Demonstration criteria require recent lab results on file.",
    "SYNTHETIC RULE: Demonstration criteria require documented contraindication to alternatives.",
]

STEP_ALTERNATIVES: list[str] = [
    "SYNTHETIC DEMO: try generic first-line alternative A",
    "SYNTHETIC DEMO: try generic first-line alternative B",
    "SYNTHETIC DEMO: try two lower-tier demo alternatives",
    "SYNTHETIC DEMO: try preferred demo alternative X or Y",
]

QUANTITY_LIMITS: list[str] = [
    "SYNTHETIC LIMIT: 30 units per 30 days",
    "SYNTHETIC LIMIT: 60 units per 30 days",
    "SYNTHETIC LIMIT: 90 units per 90 days",
    "SYNTHETIC LIMIT: 1 pen per 28 days",
    "SYNTHETIC LIMIT: 2 inhalers per 30 days",
]

FIELDNAMES: list[str] = [
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

# Synthetic copay amounts (USD) per tier, by plan.
COPAY_BY_PLAN: dict[str, dict[int, float]] = {
    "PLAN_BASIC": {1: 10.00, 2: 25.00, 3: 50.00, 4: 90.00, 5: 150.00},
    "PLAN_PLUS": {1: 5.00, 2: 20.00, 3: 40.00, 4: 75.00, 5: 120.00},
    "PLAN_PREMIUM": {1: 0.00, 2: 10.00, 3: 30.00, 4: 60.00, 5: 100.00},
}

# Plans shift tiers: Premium is more generous, Basic is less so.
PLAN_TIER_SHIFT: dict[str, int] = {"PLAN_BASIC": 1, "PLAN_PLUS": 0, "PLAN_PREMIUM": -1}


def _display_name(generic: str, brand: str) -> str:
    """Return a display drug name from generic and brand names."""
    return f"{generic} ({brand})" if brand else generic


def _build_record(
    rng: random.Random,
    record_number: int,
    med_index: int,
    generic: str,
    brand: str,
    plan_id: str,
    plan_name: str,
    base_tier: int,
) -> dict[str, Any]:
    """Build one deterministic synthetic formulary record."""
    tier = min(5, max(1, base_tier + PLAN_TIER_SHIFT[plan_id]))
    copay = COPAY_BY_PLAN[plan_id][tier]

    roll = rng.random()
    if tier == 5 and plan_id == "PLAN_BASIC" and roll < 0.25:
        coverage_status = "excluded"
    elif tier >= 4 and roll < 0.55:
        coverage_status = "restricted"
    elif tier == 3 and roll < 0.25:
        coverage_status = "restricted"
    else:
        coverage_status = "covered"

    requires_pa = False
    requires_step = False
    if coverage_status == "restricted":
        requires_pa = rng.random() < 0.85
        requires_step = rng.random() < 0.55
        if not requires_pa and not requires_step:
            requires_pa = True
    elif coverage_status == "covered" and tier >= 4:
        requires_pa = rng.random() < 0.30

    pa_criteria = rng.choice(PA_CRITERIA) if requires_pa else ""
    step_alternatives = rng.choice(STEP_ALTERNATIVES) if requires_step else ""
    quantity_limit = rng.choice(QUANTITY_LIMITS) if rng.random() < 0.6 else ""

    if coverage_status == "excluded":
        requires_pa = False
        requires_step = False
        pa_criteria = ""
        step_alternatives = ""
        quantity_limit = ""

    return {
        "record_id": f"REC_{record_number:04d}",
        "drug_name": _display_name(generic, brand),
        "generic_name": generic,
        "brand_name": brand,
        "plan_id": plan_id,
        "plan_name": plan_name,
        "tier": tier,
        "copay": f"{copay:.2f}",
        "coverage_status": coverage_status,
        "requires_pa": "true" if requires_pa else "false",
        "pa_criteria": pa_criteria,
        "requires_step_therapy": "true" if requires_step else "false",
        "step_therapy_alternatives": step_alternatives,
        "quantity_limit": quantity_limit,
        "data_source": DATA_SOURCE,
    }


def generate_records() -> list[dict[str, Any]]:
    """Generate all 240 deterministic synthetic records (80 drugs x 3 plans)."""
    rng = random.Random(SEED)
    records: list[dict[str, Any]] = []
    record_number = 1
    for med_index, (generic, brand) in enumerate(MEDICATIONS):
        base_tier = rng.randint(1, 5)
        for plan_id, plan_name in PLANS:
            records.append(
                _build_record(
                    rng,
                    record_number,
                    med_index,
                    generic,
                    brand,
                    plan_id,
                    plan_name,
                    base_tier,
                )
            )
            record_number += 1
    return records


def validate_records(records: list[dict[str, Any]]) -> None:
    """Validate record counts, uniqueness and field rules."""
    if len(MEDICATIONS) != 80:
        raise ValueError(f"Expected 80 medications, found {len(MEDICATIONS)}.")
    if len({generic for generic, _ in MEDICATIONS}) != 80:
        raise ValueError("Medication generic names must be unique.")
    if len(records) != 240:
        raise ValueError(f"Expected 240 records, found {len(records)}.")

    combos = {(r["generic_name"], r["plan_id"]) for r in records}
    if len(combos) != len(records):
        raise ValueError("Duplicate medication-plan combination found.")
    if len({r["record_id"] for r in records}) != len(records):
        raise ValueError("Duplicate record_id found.")

    for record in records:
        if set(record) != set(FIELDNAMES):
            raise ValueError(f"Unexpected fields in {record['record_id']}.")
        if not isinstance(record["tier"], int) or not 1 <= record["tier"] <= 5:
            raise ValueError(f"Invalid tier in {record['record_id']}.")
        if float(record["copay"]) < 0:
            raise ValueError(f"Negative copay in {record['record_id']}.")
        if record["coverage_status"] not in {"covered", "restricted", "excluded"}:
            raise ValueError(f"Invalid coverage_status in {record['record_id']}.")
        if record["requires_pa"] not in {"true", "false"}:
            raise ValueError(f"Invalid requires_pa in {record['record_id']}.")
        if record["requires_step_therapy"] not in {"true", "false"}:
            raise ValueError(f"Invalid requires_step_therapy in {record['record_id']}.")
        if (record["requires_pa"] == "true") != bool(record["pa_criteria"]):
            raise ValueError(f"pa_criteria mismatch in {record['record_id']}.")
        if (record["requires_step_therapy"] == "true") != bool(
            record["step_therapy_alternatives"]
        ):
            raise ValueError(f"step_therapy_alternatives mismatch in {record['record_id']}.")
        if record["data_source"] != DATA_SOURCE:
            raise ValueError(f"Invalid data_source in {record['record_id']}.")


def write_csv(records: list[dict[str, Any]], output_path: Path) -> None:
    """Write records to a CSV file, creating the parent directory if needed."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


def main() -> None:
    """Generate the synthetic formulary CSV and print a summary."""
    records = generate_records()
    validate_records(records)
    write_csv(records, OUTPUT_PATH)

    print(f"Total records: {len(records)}")
    print(f"Unique medications: {len({r['generic_name'] for r in records})}")
    print(f"Unique plans: {len({r['plan_id'] for r in records})}")
    print(f"Output file: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()