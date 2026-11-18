"""Generate the synthetic MediAssist policy PDFs used for demonstration."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from reportlab.pdfgen.canvas import Canvas

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "policies"

EXPECTED_DOC_COUNT = 10
BULLET_CHAR = "\u2022"

DISCLAIMER = "SYNTHETIC DOCUMENT — FOR DEMONSTRATION ONLY"
DISCLAIMER_DETAIL = (
    "This document was generated for software demonstration and "
    "retrieval testing. The insurer, plans, rules, thresholds and "
    "timelines described here are invented. They do not describe "
    "any real insurance policy and must not be used for medical, "
    "coverage or legal decisions. No real patient information is "
    "included."
)

INSURER = "Northwind Mutual Health"
PLANS_TEXT = (
    "MediAssist Basic (PLAN_BASIC), MediAssist Plus (PLAN_PLUS), MediAssist Premium (PLAN_PREMIUM)"
)
EFFECTIVE_DATE = "January 1, 2026"

# A section item is a paragraph (str), a bullet list (list[str]) or a table
# ({"table": rows}).
Item = str | list[str] | dict[str, list[list[str]]]
Section = tuple[str, list[Item]]

TIER_TABLE: list[list[str]] = [
    ["Tier", "Description", "Basic copay", "Plus copay", "Premium copay"],
    ["Tier 1", "Preferred generic", "$10.00", "$5.00", "$0.00"],
    ["Tier 2", "Non-preferred generic", "$25.00", "$20.00", "$10.00"],
    ["Tier 3", "Preferred brand", "$50.00", "$40.00", "$30.00"],
    ["Tier 4", "Non-preferred brand", "$90.00", "$75.00", "$60.00"],
    ["Tier 5", "Specialty", "$150.00", "$120.00", "$100.00"],
]

PA_TIMELINE_TABLE: list[list[str]] = [
    ["Request type", "Decision deadline", "Notes"],
    ["Standard", "72 hours", "Measured from receipt of a complete request."],
    [
        "Expedited",
        "24 hours",
        "Prescriber certifies that delay could seriously harm the member.",
    ],
    [
        "Incomplete request",
        "5 business days",
        "Plan notifies the prescriber of the missing items.",
    ],
    [
        "Renewal",
        "5 business days",
        "Submitted at least 30 days before the approval ends.",
    ],
]

QUANTITY_LIMITS_TABLE: list[list[str]] = [
    ["Limit label", "Applies to", "Maximum"],
    [
        "30 units per 30 days",
        "Once-daily oral tablets and capsules",
        "30 units in 30 days",
    ],
    ["60 units per 30 days", "Twice-daily oral drugs", "60 units in 30 days"],
    ["90 units per 90 days", "Mail-order maintenance drugs", "90 units in 90 days"],
    ["1 pen per 28 days", "Weekly injectable pens", "1 pen in 28 days"],
    [
        "2 inhalers per 30 days",
        "Rescue and controller inhalers",
        "2 inhalers in 30 days",
    ],
]

BIOLOGIC_AUTH_TABLE: list[list[str]] = [
    ["Stage", "Duration", "Required documentation"],
    ["Initial approval", "6 months", "Diagnosis, prior therapies, TB screen."],
    ["First reauthorization", "12 months", "Documented clinical response."],
    [
        "Later reauthorization",
        "12 months",
        "Continued response and no safety concerns.",
    ],
]

DIABETES_COVERAGE_TABLE: list[list[str]] = [
    ["Drug class", "Example drugs", "Typical synthetic rule"],
    ["Biguanide", "metformin", "Covered, Tier 1, no review."],
    ["Sulfonylurea", "glipizide", "Covered, Tier 1 or 2."],
    [
        "DPP-4 inhibitor",
        "sitagliptin, linagliptin",
        "Covered, may require step through metformin.",
    ],
    [
        "SGLT2 inhibitor",
        "empagliflozin, dapagliflozin, canagliflozin",
        "Restricted, step therapy.",
    ],
    [
        "GLP-1 agonist",
        "semaglutide, liraglutide, dulaglutide",
        "Restricted, PA, 1 pen per 28 days.",
    ],
    [
        "Insulin",
        "insulin glargine, lispro, aspart",
        "Covered, Tier 3, quantity limit by device.",
    ],
]

EXCEPTION_REVIEW_TABLE: list[list[str]] = [
    ["Review type", "Decision deadline"],
    ["Standard exception", "72 hours"],
    ["Expedited exception", "24 hours"],
    ["Notice of approval duration", "Included in the decision letter"],
]

PLAN_EXCLUSIONS_TABLE: list[list[str]] = [
    ["Category", "Basic", "Plus", "Premium"],
    ["Weight-management drugs", "Excluded", "Excluded", "Restricted, PA"],
    [
        "Select Tier 5 specialty drugs",
        "Some excluded",
        "Covered with PA",
        "Covered with PA",
    ],
    [
        "Duplicate therapy in the same class",
        "Excluded",
        "Excluded",
        "Excluded",
    ],
    [
        "Brand drug when a generic exists",
        "Excluded unless exception",
        "Tier 4",
        "Tier 3 or 4",
    ],
]

DOCS: list[dict[str, Any]] = [
    {
        "id": "MA-POL-001",
        "filename": "01_general_prescription_drug_coverage_policy.pdf",
        "title": "General Prescription Drug Coverage Policy",
        "version": "3.0",
        "references": [
            "MA-POL-002",
            "MA-POL-003",
            "MA-POL-004",
            "MA-POL-009",
            "MA-POL-010",
        ],
        "sections": [
            (
                "Purpose and Scope",
                [
                    "This policy describes how Northwind Mutual Health covers "
                    "outpatient prescription drugs under the MediAssist Basic, "
                    "MediAssist Plus and MediAssist Premium plans. It establishes "
                    "the formulary tier structure, member cost sharing, pharmacy "
                    "network rules and the general conditions that apply to every "
                    "covered prescription. Drug-class policies and utilization "
                    "management policies referenced below add to, and do not "
                    "replace, this policy.",
                ],
            ),
            (
                "Eligibility for Coverage",
                [
                    "A prescription is eligible for coverage under the synthetic "
                    "demonstration rules when all of the following conditions are "
                    "met:",
                    [
                        "The member is actively enrolled in a MediAssist plan on "
                        "the date the prescription is filled.",
                        "The drug is approved by the Food and Drug Administration "
                        "for the intended use, or the use is supported by the "
                        "synthetic reference compendium named in MA-POL-008.",
                        "The prescription is written by a licensed prescriber "
                        "acting within their scope of practice.",
                        "The drug appears on the plan formulary with a coverage "
                        "status of covered or restricted.",
                        "The drug is dispensed by a network pharmacy or the "
                        "designated mail-order pharmacy.",
                        "The drug is medically necessary and not excluded under MA-POL-010.",
                    ],
                ],
            ),
            (
                "Formulary Tier Structure and Member Cost Sharing",
                [
                    "Every formulary drug is assigned to one of five tiers. "
                    "The tier determines the member copay for a standard 30-day "
                    "supply at a network retail pharmacy. A drug may sit in a "
                    "different tier on different plans; Premium generally places "
                    "drugs one tier lower than Plus, and Basic one tier higher "
                    "than Plus.",
                    {"table": TIER_TABLE},
                    "Copay amounts are flat per fill. Mail-order fills of a "
                    "90-day supply are charged at two times the 30-day copay for "
                    "Tiers 1 through 3. Tier 4 and Tier 5 drugs are limited to a "
                    "30-day supply per fill.",
                ],
            ),
            (
                "Coverage Status Categories",
                [
                    [
                        "Covered: the drug is on the formulary and is dispensed "
                        "with the tier copay and no additional review.",
                        "Restricted: the drug is on the formulary but requires "
                        "prior authorization (MA-POL-002), step therapy "
                        "(MA-POL-003), a quantity limit (MA-POL-004), or a "
                        "combination of these.",
                        "Excluded: the drug is not covered on that plan. Members "
                        "may request a formulary exception under MA-POL-009.",
                    ],
                ],
            ),
            (
                "Pharmacy Network and Days Supply",
                [
                    "Retail network pharmacies may dispense up to a 30-day supply. "
                    "The mail-order pharmacy, Harbor Lane Mail Pharmacy, may "
                    "dispense up to a 90-day supply of eligible maintenance drugs. "
                    "Specialty drugs must be dispensed through the specialty "
                    "pharmacy network described in MA-POL-005. Out-of-network "
                    "pharmacy claims are reimbursed at 50 percent of the plan "
                    "allowed amount, less the applicable copay, except in an "
                    "emergency.",
                ],
            ),
            (
                "Exceptions",
                [
                    [
                        "Emergency supply: a network pharmacy may dispense up to a "
                        "72-hour emergency supply of a restricted drug when delayed "
                        "therapy could cause harm, pending the coverage review.",
                        "Continuity of care: new members may receive a one-time "
                        "transition fill of up to 30 days within the first 90 days "
                        "of enrollment for a drug they were already taking.",
                        "Formulary changes: members receive 60 days written notice "
                        "before a drug is moved to a higher tier or removed, and may "
                        "request a formulary exception during that period.",
                    ],
                ],
            ),
            (
                "Member Responsibilities",
                [
                    "Members must present their plan identification card at the "
                    "pharmacy, use network pharmacies whenever possible, and "
                    "notify the plan of any change in other drug coverage. "
                    "Members are responsible for copays until any annual "
                    "out-of-pocket maximum described in the plan certificate has "
                    "been reached.",
                ],
            ),
        ],
    },
    {
        "id": "MA-POL-002",
        "filename": "02_prior_authorization_requirements_policy.pdf",
        "title": "Prior Authorization Requirements Policy",
        "version": "2.4",
        "references": ["MA-POL-001", "MA-POL-003", "MA-POL-005", "MA-POL-009"],
        "sections": [
            (
                "Purpose and Scope",
                [
                    "Prior authorization (PA) is a review that Northwind Mutual "
                    "Health performs before it agrees to cover certain drugs. "
                    "This policy explains which drugs require PA, what "
                    "information must be submitted, how long reviews take and how "
                    "long approvals last. It applies to all MediAssist plans.",
                ],
            ),
            (
                "Drugs That Require Prior Authorization",
                [
                    "A drug requires PA when its formulary record shows "
                    "requires_pa as true. In general, PA applies to:",
                    [
                        "Tier 5 specialty drugs on every plan.",
                        "Tier 4 non-preferred brand drugs with a lower-cost preferred alternative.",
                        "Drugs with a high potential for misuse, such as "
                        "extended-release opioids and stimulants.",
                        "Drugs prescribed for uses other than those listed in "
                        "the product labeling.",
                        "Drugs designated by the Pharmacy and Therapeutics "
                        "Committee for clinical or cost review.",
                    ],
                ],
            ),
            (
                "Eligibility for Prior Authorization Review",
                [
                    "Only members who are actively enrolled on the date of the "
                    "request are eligible for review. The request must come from "
                    "the prescriber or the prescriber's authorized staff. Members "
                    "may ask the plan to start a request on their behalf, but the "
                    "prescriber must supply the clinical information.",
                ],
            ),
            (
                "Required Documentation",
                [
                    "A complete PA request contains each of the following items:",
                    [
                        "Member name, plan ID and member ID.",
                        "Prescriber name, National Provider Identifier and contact information.",
                        "Drug name, strength, dosage form, directions and requested duration.",
                        "Diagnosis and diagnosis code.",
                        "Relevant clinical notes, including previous drugs tried "
                        "and the outcome of each.",
                        "Supporting laboratory or imaging results dated within "
                        "the previous 90 days when the drug-specific criteria "
                        "require them.",
                    ],
                    "Typical synthetic criteria include a documented diagnosis "
                    "code on file, a documented trial of a first-line agent, a "
                    "specialist consultation note, recent laboratory results, or "
                    "a documented contraindication to the preferred alternatives.",
                ],
            ),
            (
                "Review Timelines",
                [
                    {"table": PA_TIMELINE_TABLE},
                    "If the plan does not decide within the deadline, the "
                    "request is treated as approved for the initial approval "
                    "period under the demonstration rules.",
                ],
            ),
            (
                "Approval Duration and Renewal",
                [
                    [
                        "Standard approvals last 12 months.",
                        "Initial approvals for specialty and biologic drugs last "
                        "6 months (see MA-POL-005 and MA-POL-006).",
                        "Oncology approvals follow the schedule in MA-POL-008.",
                        "Renewal requires documentation of a positive clinical "
                        "response and continued eligibility.",
                    ],
                ],
            ),
            (
                "Exceptions",
                [
                    [
                        "Emergency situations: a 72-hour supply may be dispensed without PA.",
                        "Continuity of care: members new to the plan who are "
                        "stable on a drug may receive up to 90 days of coverage "
                        "while PA is completed.",
                        "Step therapy overrides are handled in MA-POL-003 and do "
                        "not need a separate PA unless the drug also requires PA.",
                    ],
                ],
            ),
            (
                "Denials",
                [
                    "A denial notice states the specific reason, the criteria "
                    "that were not met and the member's right to appeal. Appeals "
                    "and exception requests are governed by MA-POL-009.",
                ],
            ),
        ],
    },
    {
        "id": "MA-POL-003",
        "filename": "03_step_therapy_requirements_policy.pdf",
        "title": "Step Therapy Requirements Policy",
        "version": "2.1",
        "references": ["MA-POL-001", "MA-POL-002", "MA-POL-007", "MA-POL-009"],
        "sections": [
            (
                "Purpose and Scope",
                [
                    "Step therapy requires a member to try one or more lower-cost "
                    "or preferred drugs before the plan covers a higher-cost drug "
                    "in the same therapeutic class. This policy defines when step "
                    "therapy applies, what counts as an adequate trial and when a "
                    "step requirement can be overridden. It applies to drugs whose "
                    "formulary record shows requires_step_therapy as true.",
                ],
            ),
            (
                "Eligibility and Application",
                [
                    "Step therapy applies to new starts. A member who has filled "
                    "the requested drug within the previous 120 days under any "
                    "plan is not required to repeat the steps. Step therapy does "
                    "not apply to drugs dispensed under the emergency supply or "
                    "transition fill provisions of MA-POL-001.",
                ],
            ),
            (
                "Adequate Trial Requirements",
                [
                    "A step is considered satisfied when the member has done any of the following:",
                    [
                        "Completed a trial of the preferred drug at a clinically "
                        "appropriate dose for at least 30 days, or 90 days for drug "
                        "classes designated as slow-acting.",
                        "Stopped the preferred drug because of a documented adverse "
                        "reaction or intolerance.",
                        "Had the preferred drug fail to achieve the therapeutic goal, "
                        "documented with dates and results.",
                    ],
                    "Pharmacy claims history is used first. If claims history is "
                    "not available, the prescriber may supply chart notes.",
                ],
            ),
            (
                "Step Override Criteria",
                [
                    "The plan will override a step requirement when the prescriber "
                    "documents at least one of the following:",
                    [
                        "The preferred drug is contraindicated for the member.",
                        "The member is stable on the requested drug and a change "
                        "is expected to cause harm.",
                        "The preferred drug is expected to be ineffective based on "
                        "the member's known characteristics.",
                        "The member's condition requires a drug with a specific "
                        "mechanism of action.",
                    ],
                ],
            ),
            (
                "Synthetic Example Step Sequences",
                [
                    "The following sequences are invented for demonstration. For "
                    "a Tier 4 brand cholesterol drug, the first step is a Tier 1 "
                    "generic statin for 30 days; for a Tier 4 brand "
                    "anticoagulant, the first step is the preferred Tier 2 "
                    "anticoagulant. For drugs with listed alternatives, the "
                    "step_therapy_alternatives field of the formulary record "
                    "names the demonstration alternatives, for example preferred "
                    "demo alternative X or Y, or two lower-tier demo alternatives.",
                ],
            ),
            (
                "Timelines",
                [
                    "Step therapy override requests are decided within 72 hours, "
                    "or 24 hours when expedited. Approved overrides last for the "
                    "same period as a prior authorization for the drug.",
                ],
            ),
            (
                "Exceptions",
                [
                    [
                        "A member who changes plans mid-treatment keeps the benefit "
                        "of any step already satisfied.",
                        "Step therapy does not apply to drugs used to treat a "
                        "life-threatening condition where delay would be harmful, "
                        "as certified by the prescriber.",
                        "Members may appeal a step therapy denial under MA-POL-009.",
                    ],
                ],
            ),
        ],
    },
    {
        "id": "MA-POL-004",
        "filename": "04_quantity_limits_policy.pdf",
        "title": "Quantity Limits Policy",
        "version": "1.8",
        "references": ["MA-POL-001", "MA-POL-007", "MA-POL-009"],
        "sections": [
            (
                "Purpose and Scope",
                [
                    "Quantity limits cap the amount of a drug the plan covers in a "
                    "given period. They exist for demonstration purposes to model "
                    "safety, dosing and supply-management controls. This policy "
                    "applies to every drug whose formulary record includes a "
                    "quantity_limit value.",
                ],
            ),
            (
                "Types of Quantity Limits",
                [
                    [
                        "Per-fill limit: the maximum units dispensed in a single fill.",
                        "Per-period limit: the maximum units over a stated period, "
                        "such as 30 or 90 days.",
                        "Daily dose limit: the maximum number of units per day, "
                        "based on labeled dosing.",
                        "Device limit: the maximum number of pens, inhalers or devices per period.",
                    ],
                ],
            ),
            (
                "Standard Synthetic Limits",
                [
                    {"table": QUANTITY_LIMITS_TABLE},
                ],
            ),
            (
                "Eligibility for a Quantity Limit Override",
                [
                    "A member is eligible to request an override when the "
                    "prescriber documents a medically necessary dose above the "
                    "standard limit. The request must include the diagnosis, the "
                    "requested quantity, the dosing rationale and previous doses "
                    "tried. Overrides are reviewed within 72 hours, or 24 hours "
                    "when expedited.",
                ],
            ),
            (
                "Dose Optimization",
                [
                    "The plan encourages use of the highest strength that meets "
                    "the prescribed dose. When two or more units of a lower "
                    "strength are prescribed and a single higher-strength unit "
                    "is available at the same daily dose, the pharmacy may "
                    "contact the prescriber to switch.",
                ],
            ),
            (
                "Exceptions",
                [
                    [
                        "Vacation supply: members may receive one early refill of "
                        "up to 30 days per calendar year when traveling, with "
                        "notice of at least 7 days.",
                        "Lost or damaged medication: one replacement fill per 12 "
                        "months, subject to review.",
                        "Dose titration: temporary limit increases of up to 60 days "
                        "are allowed during titration.",
                        "Further exceptions follow the process in MA-POL-009.",
                    ],
                ],
            ),
            (
                "Interaction with Other Policies",
                [
                    "Quantity limits for diabetes injectables are described "
                    "further in MA-POL-007. A quantity limit does not replace any "
                    "prior authorization or step therapy requirement on the same "
                    "drug.",
                ],
            ),
        ],
    },
    {
        "id": "MA-POL-005",
        "filename": "05_specialty_medication_coverage_policy.pdf",
        "title": "Specialty Medication Coverage Policy",
        "version": "2.2",
        "references": ["MA-POL-002", "MA-POL-006", "MA-POL-008", "MA-POL-009"],
        "sections": [
            (
                "Purpose and Scope",
                [
                    "This policy covers specialty medications, which are "
                    "high-cost drugs or drugs that need special handling, "
                    "administration or monitoring. Specialty drugs are placed in "
                    "Tier 5 on all MediAssist plans.",
                ],
            ),
            (
                "Definition of a Specialty Medication",
                [
                    "For demonstration purposes, a drug is a specialty "
                    "medication when it meets at least two of the following "
                    "conditions:",
                    [
                        "The synthetic monthly plan cost exceeds $1,000.",
                        "The drug treats a complex, chronic or rare condition.",
                        "The drug requires refrigeration or special handling.",
                        "The drug requires clinical monitoring or member education for safe use.",
                        "The drug is an injectable, infusion or specialty oral product.",
                    ],
                ],
            ),
            (
                "Eligibility",
                [
                    "Members must be enrolled and have a diagnosis that the drug "
                    "is intended to treat. Prior authorization is required for "
                    "every specialty medication (see MA-POL-002). The prescriber "
                    "should be a specialist in the relevant condition or consult "
                    "with one.",
                ],
            ),
            (
                "Specialty Pharmacy Network",
                [
                    "Specialty drugs must be dispensed by the plan's specialty "
                    "pharmacy network, which in this synthetic scenario consists "
                    "of Meridian Specialty Rx and Cascade Infusion Pharmacy. "
                    "Fills from other pharmacies are not covered except under the "
                    "emergency supply provision.",
                ],
            ),
            (
                "Dispensing Rules",
                [
                    [
                        "Supply is limited to 30 days per fill.",
                        "The first fill is dispensed as a 14-day trial supply for "
                        "new starts to confirm tolerability.",
                        "Members are contacted by a specialty pharmacist before each refill.",
                        "Refills may be requested when 75 percent of the previous "
                        "supply should have been used.",
                    ],
                ],
            ),
            (
                "Cost Sharing",
                [
                    "Specialty drugs carry the Tier 5 copay: $150.00 on Basic, "
                    "$120.00 on Plus and $100.00 on Premium. Manufacturer copay "
                    "assistance does not count toward the annual out-of-pocket "
                    "maximum in this demonstration policy. Some specialty drugs "
                    "are excluded on the Basic plan; see MA-POL-010.",
                ],
            ),
            (
                "Exceptions",
                [
                    [
                        "A 72-hour emergency supply may be dispensed by any network pharmacy.",
                        "Members who cannot use the network specialty pharmacy "
                        "because of urgent clinical need may request an exception "
                        "under MA-POL-009.",
                    ],
                ],
            ),
        ],
    },
    {
        "id": "MA-POL-006",
        "filename": "06_biologic_medication_coverage_policy.pdf",
        "title": "Biologic Medication Coverage Policy",
        "version": "2.0",
        "references": ["MA-POL-002", "MA-POL-003", "MA-POL-005", "MA-POL-009"],
        "sections": [
            (
                "Purpose and Scope",
                [
                    "This policy sets synthetic coverage criteria for biologic "
                    "medications used for immune-mediated conditions. Examples "
                    "named for demonstration include adalimumab, etanercept, "
                    "ustekinumab, secukinumab, dupilumab and omalizumab. The "
                    "rules below are invented and do not reflect actual insurer "
                    "policy or clinical guidance.",
                ],
            ),
            (
                "Eligibility Criteria",
                [
                    "A member is eligible for biologic coverage when all of the "
                    "following are documented:",
                    [
                        "A diagnosis made or confirmed by a specialist such as a "
                        "rheumatologist, dermatologist, gastroenterologist or "
                        "allergist.",
                        "Failure, intolerance or contraindication to at least one "
                        "conventional therapy, for example methotrexate for "
                        "inflammatory arthritis.",
                        "A negative tuberculosis screen dated within the previous 12 months.",
                        "No active serious infection at the time of the request.",
                        "The biologic will not be combined with another biologic "
                        "for the same condition.",
                    ],
                ],
            ),
            (
                "Preferred Products and Biosimilars",
                [
                    "The plan designates one preferred product in each class. "
                    "Non-preferred biologics require a step through the "
                    "preferred product under MA-POL-003. Where a biosimilar is "
                    "available, the biosimilar is the preferred product on all "
                    "plans.",
                ],
            ),
            (
                "Initial Authorization and Reauthorization",
                [
                    {"table": BIOLOGIC_AUTH_TABLE},
                    "A clinical response is shown by improvement in a disease "
                    "activity measure chosen by the prescriber, or by a reduction "
                    "in symptoms documented in the chart.",
                ],
            ),
            (
                "Dosing and Quantity",
                [
                    "Doses must follow the labeled schedule. Loading doses are "
                    "allowed for the first fill only. Quantity limits in "
                    "MA-POL-004 apply, for example 1 pen per 28 days for weekly "
                    "pens.",
                ],
            ),
            (
                "Exceptions",
                [
                    [
                        "Members stable on a non-preferred biologic when joining "
                        "the plan may continue it for 90 days during transition.",
                        "A step through the preferred biologic is waived when it "
                        "is contraindicated.",
                        "Denials may be appealed under MA-POL-009.",
                    ],
                ],
            ),
        ],
    },
    {
        "id": "MA-POL-007",
        "filename": "07_diabetes_medication_coverage_policy.pdf",
        "title": "Diabetes Medication Coverage Policy",
        "version": "2.3",
        "references": ["MA-POL-001", "MA-POL-002", "MA-POL-003", "MA-POL-004"],
        "sections": [
            (
                "Purpose and Scope",
                [
                    "This policy describes synthetic coverage rules for drugs "
                    "that treat diabetes, including metformin, sulfonylureas, "
                    "DPP-4 inhibitors, SGLT2 inhibitors, GLP-1 receptor agonists "
                    "and insulins. It is a demonstration of policy structure only "
                    "and contains no medical advice.",
                ],
            ),
            (
                "Eligibility",
                [
                    "Members are eligible when a prescriber documents a diagnosis "
                    "of type 1 or type 2 diabetes. For non-insulin drugs other "
                    "than metformin, the request should include a hemoglobin A1C "
                    "result dated within the previous 90 days.",
                ],
            ),
            (
                "Coverage by Drug Class",
                [
                    {"table": DIABETES_COVERAGE_TABLE},
                ],
            ),
            (
                "Prior Authorization and Step Therapy",
                [
                    "GLP-1 receptor agonists require prior authorization under "
                    "MA-POL-002 with documentation of a type 2 diabetes diagnosis "
                    "and a trial of metformin for at least 90 days, unless "
                    "metformin is contraindicated. SGLT2 inhibitors follow the "
                    "step rules of MA-POL-003.",
                ],
            ),
            (
                "Quantity Limits and Supplies",
                [
                    "Injectable pens are limited as described in MA-POL-004. Test "
                    "strips, lancets and pen needles are covered as supplies with "
                    "a 90-day maximum per fill.",
                ],
            ),
            (
                "Exclusions Specific to Diabetes Drugs",
                [
                    "GLP-1 drugs prescribed only for weight management are not "
                    "covered under this policy and are addressed in MA-POL-010. "
                    "Compounded versions of diabetes drugs are not covered.",
                ],
            ),
            (
                "Exceptions",
                [
                    [
                        "Insulin may be dispensed in an emergency without prior "
                        "review, up to a 30-day supply.",
                        "Members pregnant or planning pregnancy may request an "
                        "exception to a step requirement.",
                        "Members with documented kidney or heart disease may be "
                        "exempt from certain steps when the prescriber certifies "
                        "the need.",
                    ],
                ],
            ),
        ],
    },
    {
        "id": "MA-POL-008",
        "filename": "08_oncology_medication_coverage_policy.pdf",
        "title": "Oncology Medication Coverage Policy",
        "version": "1.9",
        "references": ["MA-POL-002", "MA-POL-005", "MA-POL-009"],
        "sections": [
            (
                "Purpose and Scope",
                [
                    "This policy governs coverage of oral and self-administered "
                    "cancer drugs under the MediAssist plans. "
                    "Facility-administered chemotherapy is handled under the "
                    "medical benefit and is outside the scope of this document. "
                    "All rules are synthetic.",
                ],
            ),
            (
                "Eligibility",
                [
                    "Coverage is available for members with a confirmed cancer "
                    "diagnosis and a treatment plan from an oncologist or "
                    "hematologist. The drug must be used for an indication that "
                    "is FDA-approved or supported by the synthetic reference "
                    "compendium, called the Northwind Oncology Reference, which "
                    "is a fictional resource used only for this demonstration.",
                ],
            ),
            (
                "Documentation Requirements",
                [
                    [
                        "Pathology report or equivalent confirming the diagnosis.",
                        "Disease stage and treatment intent.",
                        "Biomarker or genetic test results when required by the "
                        "drug-specific criteria.",
                        "Performance status and relevant laboratory values.",
                        "Prior cancer treatments and outcomes.",
                    ],
                ],
            ),
            (
                "Review Timelines and Approval Duration",
                [
                    "Oncology PA requests are decided within 24 hours because of "
                    "the urgent nature of treatment. Initial approvals last 6 "
                    "months. Renewal requires documentation that the disease has "
                    "not progressed and the member is tolerating treatment.",
                ],
            ),
            (
                "Dispensing",
                [
                    "Oral oncology drugs are dispensed through the specialty "
                    "network in MA-POL-005. Initial fills may be limited to 14 "
                    "days when the drug has a high rate of early discontinuation. "
                    "Dose adjustments within the labeled range do not require a "
                    "new request.",
                ],
            ),
            (
                "Supportive Care Drugs",
                [
                    "Anti-nausea drugs such as ondansetron are covered at Tier 1 "
                    "with a quantity limit of 30 units per 30 days, and may be "
                    "extended to 60 units per 30 days during active chemotherapy.",
                ],
            ),
            (
                "Exceptions",
                [
                    [
                        "Members already stable on an oncology drug at enrollment "
                        "may continue for 90 days.",
                        "Use in a clinical trial is covered only for the "
                        "standard-of-care drugs in the protocol.",
                        "Denials may be appealed under MA-POL-009 with an "
                        "expedited 72-hour review.",
                    ],
                ],
            ),
        ],
    },
    {
        "id": "MA-POL-009",
        "filename": "09_formulary_exceptions_and_appeals_policy.pdf",
        "title": "Formulary Exceptions and Appeals Policy",
        "version": "2.5",
        "references": [
            "MA-POL-001",
            "MA-POL-002",
            "MA-POL-003",
            "MA-POL-004",
            "MA-POL-010",
        ],
        "sections": [
            (
                "Purpose and Scope",
                [
                    "This policy describes how members and prescribers can request "
                    "an exception to formulary rules and how to appeal an adverse "
                    "coverage decision. It applies to all MediAssist plans.",
                ],
            ),
            (
                "Types of Exception Requests",
                [
                    [
                        "Formulary exception: coverage of a drug that is excluded "
                        "or not on the formulary.",
                        "Tiering exception: coverage of a drug at a lower cost-sharing tier.",
                        "Step therapy exception: waiver of a required step (see MA-POL-003).",
                        "Quantity limit exception: coverage above a standard limit "
                        "(see MA-POL-004).",
                    ],
                ],
            ),
            (
                "Eligibility to Request",
                [
                    "Members, their authorized representatives and prescribers may "
                    "request an exception. The request must include a supporting "
                    "statement from the prescriber explaining why the formulary "
                    "alternatives are or would be ineffective, or would cause "
                    "adverse effects.",
                ],
            ),
            (
                "Exception Review Timelines",
                [
                    {"table": EXCEPTION_REVIEW_TABLE},
                    "An approved exception lasts for the remainder of the plan "
                    "year, or 12 months, whichever is longer.",
                ],
            ),
            (
                "Internal Appeals",
                [
                    "A member may appeal any denial within 180 days of the denial notice.",
                    [
                        "Level 1 appeal: reviewed by a clinician who was not "
                        "involved in the original decision. Decision within 30 days "
                        "for pre-service requests and 72 hours when expedited.",
                        "Level 2 appeal: reviewed by the Appeals Committee, "
                        "including a physician or pharmacist reviewer in the same "
                        "specialty where possible. Decision within 30 days.",
                    ],
                ],
            ),
            (
                "External Review",
                [
                    "After the internal appeals are exhausted, a member may "
                    "request an independent external review. The independent "
                    "organization decides within 45 days, or 72 hours for "
                    "expedited cases. The decision is binding on the plan under "
                    "the demonstration rules.",
                ],
            ),
            (
                "Exceptions to Appeal Rights",
                [
                    [
                        "Services that are never covered by the plan certificate, "
                        "as opposed to drugs not on the formulary, cannot be "
                        "changed through an exception.",
                        "Drugs excluded by law or by MA-POL-010 category may be "
                        "reviewed only for formulary exceptions when the exclusion "
                        "list notes that the category is eligible.",
                    ],
                ],
            ),
            (
                "Member Rights",
                [
                    "Members have the right to receive the reason for a denial in "
                    "writing, to have copies of the criteria used, to submit "
                    "additional information and to have an authorized "
                    "representative act on their behalf.",
                ],
            ),
        ],
    },
    {
        "id": "MA-POL-010",
        "filename": "10_formulary_exclusions_policy.pdf",
        "title": "Formulary Exclusions Policy",
        "version": "1.7",
        "references": ["MA-POL-001", "MA-POL-005", "MA-POL-007", "MA-POL-009"],
        "sections": [
            (
                "Purpose and Scope",
                [
                    "This policy lists categories of drugs that are excluded from "
                    "coverage under the MediAssist plans and explains how plan "
                    "differences affect exclusions. A drug with coverage status "
                    "excluded in the formulary record is not covered on that plan.",
                ],
            ),
            (
                "Excluded Categories on All Plans",
                [
                    [
                        "Drugs used for cosmetic purposes, such as hair removal or "
                        "skin-appearance products.",
                        "Drugs that are experimental, investigational or not approved by the FDA.",
                        "Over-the-counter products unless specifically listed on the formulary.",
                        "Bulk powders and compounded drugs when a commercially "
                        "available equivalent exists.",
                        "Drugs for conditions covered by workers' compensation or "
                        "other primary coverage.",
                        "Replacement of lost drugs beyond the limit in MA-POL-004.",
                        "Drugs dispensed by a non-network pharmacy, except in an emergency.",
                    ],
                ],
            ),
            (
                "Plan-Specific Exclusions",
                [
                    {"table": PLAN_EXCLUSIONS_TABLE},
                ],
            ),
            (
                "Eligibility to Receive an Exception",
                [
                    "Not every exclusion can be waived. A formulary exception "
                    "request may be reviewed for plan-specific exclusions and for "
                    "brand drugs with an available generic. Requests for cosmetic "
                    "drugs, experimental drugs and drugs covered by other primary "
                    "coverage cannot be approved through MA-POL-009.",
                ],
            ),
            (
                "Mid-Year Changes",
                [
                    "The plan may add drugs to the formulary at any time. Removal "
                    "of a drug or a move to an excluded status occurs only at the "
                    "start of a plan year, with 60 days notice, unless safety "
                    "concerns or market withdrawal require an earlier change.",
                ],
            ),
            (
                "Exceptions",
                [
                    [
                        "Members stable on a drug that becomes excluded may "
                        "receive a transition supply of up to 30 days.",
                        "Members with a documented contraindication to every "
                        "covered alternative may request a formulary exception "
                        "under MA-POL-009.",
                        "Specialty drugs excluded on Basic remain subject to "
                        "MA-POL-005 on other plans.",
                    ],
                ],
            ),
        ],
    },
]


def build_styles() -> dict[str, ParagraphStyle]:
    """Create the paragraph styles used in every document."""
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "PolicyTitle",
            parent=base["Title"],
            fontSize=20,
            leading=24,
            spaceAfter=6,
        ),
        "insurer": ParagraphStyle(
            "Insurer",
            parent=base["Normal"],
            fontSize=11,
            alignment=TA_CENTER,
            spaceAfter=10,
        ),
        "disclaimer": ParagraphStyle(
            "Disclaimer",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#B00020"),
        ),
        "disclaimer_detail": ParagraphStyle(
            "DisclaimerDetail",
            parent=base["Normal"],
            fontSize=8.5,
            leading=11,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#B00020"),
        ),
        "heading": ParagraphStyle(
            "SectionHeading",
            parent=base["Heading2"],
            fontSize=13,
            leading=16,
            spaceBefore=14,
            spaceAfter=6,
            textColor=colors.HexColor("#1F3A5F"),
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontSize=10,
            leading=14,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["BodyText"],
            fontSize=10,
            leading=14,
            leftIndent=22,
            bulletIndent=8,
            spaceAfter=3,
        ),
        "cell": ParagraphStyle(
            "Cell",
            parent=base["BodyText"],
            fontSize=9,
            leading=11,
        ),
        "cell_header": ParagraphStyle(
            "CellHeader",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
        ),
    }


def make_table(
    rows: list[list[str]],
    styles: dict[str, ParagraphStyle],
    width: float,
) -> Table:
    """Build a wrapped, styled table from rows (first row is the header)."""
    data = [
        [Paragraph(escape(cell), styles["cell_header" if r == 0 else "cell"]) for cell in row]
        for r, row in enumerate(rows)
    ]
    column_count = len(rows[0])
    col_width = width / column_count
    table = Table(data, colWidths=[col_width] * column_count, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6ECF3")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def bullet_paragraph(text: str, styles: dict[str, ParagraphStyle]) -> Paragraph:
    """Build a single bulleted paragraph."""
    return Paragraph(escape(text), styles["bullet"], bulletText=BULLET_CHAR)


def build_story(
    doc: dict[str, Any],
    titles: dict[str, str],
    styles: dict[str, ParagraphStyle],
    width: float,
) -> list[Any]:
    """Assemble the Platypus flowables for one policy document."""
    story: list[Any] = []

    banner = Table(
        [
            [Paragraph(escape(DISCLAIMER), styles["disclaimer"])],
            [Paragraph(escape(DISCLAIMER_DETAIL), styles["disclaimer_detail"])],
        ],
        colWidths=[width],
    )
    banner.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor("#B00020")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FDECEE")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(banner)
    story.append(Spacer(1, 14))

    story.append(Paragraph(escape(doc["title"]), styles["title"]))
    story.append(Paragraph(escape(INSURER), styles["insurer"]))

    metadata = [
        ["Field", "Value"],
        ["Document ID", doc["id"]],
        ["Title", doc["title"]],
        ["Insurer", INSURER],
        ["Applies to plans", PLANS_TEXT],
        ["Effective date", EFFECTIVE_DATE],
        ["Version", doc["version"]],
        ["Data source", "SYNTHETIC_DEMO_DATA"],
    ]
    meta_table = make_table(metadata, styles, width)
    story.append(meta_table)
    story.append(Spacer(1, 6))

    for number, (heading, items) in enumerate(doc["sections"], start=1):
        heading_text = f"Section {number}. {heading}"
        story.append(Paragraph(escape(heading_text), styles["heading"]))
        for item in items:
            if isinstance(item, str):
                story.append(Paragraph(escape(item), styles["body"]))
            elif isinstance(item, list):
                for bullet in item:
                    story.append(bullet_paragraph(bullet, styles))
                story.append(Spacer(1, 4))
            else:
                story.append(make_table(item["table"], styles, width))
                story.append(Spacer(1, 8))

    next_number = len(doc["sections"]) + 1
    related_heading = f"Section {next_number}. Related Synthetic Policies"
    story.append(Paragraph(escape(related_heading), styles["heading"]))
    story.append(
        Paragraph(
            escape("This policy should be read together with the following synthetic documents:"),
            styles["body"],
        )
    )
    for ref in doc["references"]:
        story.append(bullet_paragraph(f"{ref}: {titles[ref]}", styles))
    story.append(Spacer(1, 4))

    revision_heading = f"Section {next_number + 1}. Revision History"
    story.append(Paragraph(escape(revision_heading), styles["heading"]))
    revision_rows = [
        ["Version", "Effective date", "Summary of change"],
        [
            doc["version"],
            EFFECTIVE_DATE,
            "Current synthetic demonstration version.",
        ],
        ["Prior", "January 1, 2025", "Previous synthetic version, superseded."],
    ]
    story.append(make_table(revision_rows, styles, width))
    return story


def make_page_decorator(doc_id: str) -> Callable[[Canvas, SimpleDocTemplate], None]:
    """Return a callback that draws the disclaimer footer and page number."""

    def decorate(canvas: Canvas, document: SimpleDocTemplate) -> None:
        margin = 0.75 * inch
        footer_y = 0.5 * inch
        canvas.saveState()
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(colors.HexColor("#B00020"))
        canvas.drawString(margin, footer_y, f"{DISCLAIMER} | {doc_id}")
        canvas.setFillColor(colors.black)
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(LETTER[0] - margin, footer_y, f"Page {document.page}")
        canvas.restoreState()

    return decorate


def generate_pdf(
    doc: dict[str, Any],
    titles: dict[str, str],
    output_dir: Path,
) -> Path:
    """Generate one policy PDF and return its path."""
    styles = build_styles()
    path = output_dir / doc["filename"]
    pdf = SimpleDocTemplate(
        str(path),
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.9 * inch,
        title=f"{doc['id']} {doc['title']} (SYNTHETIC)",
        author=f"{INSURER} (synthetic)",
        subject=DISCLAIMER,
        invariant=True,  # fixed timestamps and IDs so output is reproducible
    )
    width = LETTER[0] - 1.5 * inch
    story = build_story(doc, titles, styles, width)
    decorator = make_page_decorator(doc["id"])
    pdf.build(story, onFirstPage=decorator, onLaterPages=decorator)
    return path


def validate_docs() -> None:
    """Check document count, unique IDs and valid cross-references."""
    if len(DOCS) != EXPECTED_DOC_COUNT:
        msg = f"Expected {EXPECTED_DOC_COUNT} documents, found {len(DOCS)}."
        raise ValueError(msg)
    ids = [doc["id"] for doc in DOCS]
    if len(set(ids)) != len(ids):
        msg = "Duplicate document IDs found."
        raise ValueError(msg)
    for doc in DOCS:
        for ref in doc["references"]:
            if ref not in ids:
                msg = f"{doc['id']} references unknown document {ref}."
                raise ValueError(msg)
            if ref == doc["id"]:
                msg = f"{doc['id']} references itself."
                raise ValueError(msg)


def main() -> None:
    """Generate all synthetic policy PDFs and print a summary."""
    validate_docs()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    titles = {doc["id"]: doc["title"] for doc in DOCS}

    generated: list[tuple[str, str, Path]] = []
    for doc in DOCS:
        path = generate_pdf(doc, titles, OUTPUT_DIR)
        generated.append((doc["id"], doc["title"], path))

    print(f"Generated {len(generated)} synthetic policy PDFs ({DISCLAIMER}):")
    for doc_id, title, path in generated:
        print(f"  {doc_id}  {title}  ->  {path}")
    print(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
