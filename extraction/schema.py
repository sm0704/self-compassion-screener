"""Structured schema for full-text data extraction.

Mirrors the Covidence extraction form's domains and the `data_extraction_sheet.docx`
codebook. Every leaf field is an `Evidence` object rather than a bare value, so the
reviewer can check a quote against a page number instead of re-reading the paper.

The nesting — study-level fields, then `outcomes[]`, then `effects[]` inside each
outcome — is deliberate: it matches how Covidence models the data via the "Timepoints"
(really "Extra Effects") control. One outcome card in the UI = one academic variable =
one Outcomes entry in Covidence; the number of effects inside it is the Timepoints count.

Values are strings throughout, never floats. That preserves what the paper actually
printed ("-.17", "< .01", "61.1%") and avoids the float-coercion artifacts that turn
61.1% into 0.61099999999999999.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Confidence = Literal["high", "medium", "low", "absent"]


class Evidence(BaseModel):
    """One extracted field, with its provenance."""

    value: Optional[str] = Field(
        None,
        description=(
            "The value exactly as the paper reports it, or the codebook code where one "
            "applies. Null when the paper does not report it — never guess or infer."
        ),
    )
    page: Optional[str] = Field(
        None,
        description="Where it came from, e.g. 'p. 4', 'Table 2 (p. 5)', 'Figure 1'.",
    )
    quote: Optional[str] = Field(
        None,
        description="Short verbatim quote from the paper supporting the value.",
    )
    confidence: Confidence = Field(
        description=(
            "high = stated explicitly; medium = clear but needs light interpretation; "
            "low = ambiguous, reviewer should check; absent = the paper does not report it."
        )
    )
    note: Optional[str] = Field(
        None,
        description=(
            "Only when useful: why this is uncertain, or — when value is null — which "
            "section you read that failed to report it."
        ),
    )


# ─────────────────────────── study-level domains ───────────────────────────


class Identification(BaseModel):
    title: Evidence
    citation: Evidence = Field(description="APA7 in-text form, e.g. 'Seekis et al. (2023)'.")
    year: Evidence
    country: Evidence = Field(description="If multiple, where the SAMPLE was collected.")
    article_type: Evidence = Field(
        description=(
            "1=journal article, 2=doctorate thesis, 3=master's thesis, "
            "4=undergraduate thesis, 5=conference proceedings."
        )
    )
    aim: Evidence = Field(description="The paper's overall focus or research question.")


class Methods(BaseModel):
    design_type: Evidence = Field(
        description="cross-sectional, PR/LONG (prospective/longitudinal), RCT, or N-RCT."
    )
    n_timepoints: Evidence = Field(
        description=(
            "Actual measurement waves in the study design (pre/post = 2). NOT the "
            "Covidence Outcomes 'Timepoints' control, which means extra effects."
        )
    )
    intervention_type: Evidence = Field(
        description="Program name plus its source citation, if the study had one."
    )
    intervention_duration: Evidence


class Population(BaseModel):
    n_study: Evidence = Field(description="Total participants in the study.")
    student_type: Evidence = Field(
        description=(
            "1=grades 1-8 (primary/elementary/middle), 2=grades 9-12 (high school), "
            "3=undergraduate, 4=graduate/professional/diploma."
        )
    )
    age_mean: Evidence
    age_sd: Evidence
    age_range: Evidence
    pct_female: Evidence
    sample_specification: Evidence = Field(
        description="e.g. 'nursing students', 'Year 7 and 8 class', 'students with depression'."
    )
    sampling_method: Evidence = Field(description="convenience, random, etc. NS if not stated.")


class SelfCompassionMeasure(BaseModel):
    """The Covidence 'Interventions' domain — the SC measure, not the program."""

    measure_format: Evidence = Field(
        description="Scale name and item count, e.g. 'SCS (26 item)', 'SCS-SF (12 item)'."
    )
    measure_version: Evidence = Field(description="original, adapted, or translated.")
    total_score_used: Evidence = Field(description="Y or N.")
    subscales_reported: Evidence = Field(description="Y or N — subscales with effects reported.")
    scs_reporting: Evidence = Field(
        description=(
            "1=total self-compassion, 2=paired subscales, "
            "3=positive and negative composite, 4=individual subscales."
        )
    )
    scs_valence: Evidence = Field(description="POS or NEG.")
    scoring: Evidence = Field(description="continuous or categorical.")


# ────────────────────────────── results data ──────────────────────────────


class Supplemental(BaseModel):
    """Only populated for mean comparisons or where a conversion is needed."""

    t_value: Evidence
    df_numerator: Evidence = Field(description="For F: k - 1, where k = number of groups.")
    df_denominator: Evidence = Field(description="For F: n - k.")
    f_value: Evidence
    cohens_d: Evidence
    mean_group1: Evidence
    mean_group2: Evidence
    sd_group1: Evidence
    sd_group2: Evidence


class Effect(BaseModel):
    variables: Evidence = Field(
        description="e.g. 'Self-compassion and school connectedness'."
    )
    effect_type: Evidence = Field(
        description="Statistic and its label, e.g. 'Pearson correlation; r'."
    )
    effect_value: Evidence = Field(
        description="The raw value as printed, sign preserved (e.g. '-0.17')."
    )
    p_value: Evidence = Field(description="e.g. '< .05', '< .01', '< .001', 'ns'.")
    effect_direction: Evidence = Field(
        description="POS = higher SC with higher academic variable; NEG = the inverse."
    )
    effect_significance: Evidence = Field(
        description="NULL = non-significant, POS = significant positive, NEG = significant negative."
    )
    n_effect: Evidence = Field(
        description="Participants behind THIS statistic — often smaller than study N."
    )
    notes_adjusted: Evidence = Field(description="adjusted or unadjusted.")
    notes_design: Evidence = Field(
        description="cross-sectional, prospective, or change score."
    )
    narrative_summary: Evidence = Field(
        description="One sentence describing the effect in plain language."
    )
    supplemental: Supplemental
    ladder_rung: int = Field(
        description=(
            "Priority ladder rung this statistic sits on: 1=Pearson/Spearman r, "
            "2=change-score correlation, 3=standardized regression beta, "
            "4=standardized SEM/path coefficient, 5=mean comparison (t, F)."
        )
    )
    ladder_rationale: str = Field(
        description="Why this rung was the highest available for this SC x academic pair."
    )


class Outcome(BaseModel):
    """One academic-functioning variable = one Covidence Outcomes entry."""

    academic_variable_name: Evidence = Field(
        description="The construct as the authors name it."
    )
    outcome_name_coded: Evidence = Field(description="Reviewer's normalised name for it.")
    table_name: Evidence
    measure_used: Evidence = Field(description="Measure name plus citation.")
    measure_description: Evidence = Field(description="Item count and a short description.")
    outcome_reporting: Evidence = Field(description="SR = self-report, OR = other-report.")
    adaptations: Evidence = Field(
        description="Was the measure modified or adapted? NS if not stated."
    )
    af_valence: Evidence = Field(
        description="POS = measures a positive outcome, NEG = a negative one."
    )
    outcome_notes: Evidence
    effects: List[Effect] = Field(
        description=(
            "Every effect extracted for this variable. The count here is what the "
            "Covidence 'Timepoints' control must be set to."
        )
    )


# ─────────────────────────── review-support blocks ───────────────────────────


class RejectedOutcome(BaseModel):
    name: str
    reason: str = Field(description="Why this is not academic functioning.")


class DroppedEffect(BaseModel):
    description: str
    superseded_by: str = Field(
        description="The higher-ladder effect that was extracted instead."
    )


class Flag(BaseModel):
    level: Literal["blank", "uncertain", "unreadable", "extra", "conflict"] = Field(
        description=(
            "blank = no value in the paper; uncertain = below ~85% confidence; "
            "unreadable = could not be read (image-only table, OCR failure); "
            "extra = found but no matching field; conflict = text and table disagree."
        )
    )
    field: str
    message: str


class Coverage(BaseModel):
    pages_total: str
    sections_read: List[str]
    tables_inspected: List[str] = Field(description="By number and caption.")
    figures_inspected: List[str]
    unreadable: List[str] = Field(
        description="Anything that could not be read, so the reviewer checks it manually."
    )


# ──────────────────────────────── pass 1 ────────────────────────────────


class CandidateEffect(BaseModel):
    academic_variable: str
    sc_variable: str = Field(
        description="'total self-compassion', or the named subscale/dimension."
    )
    statistic_type: str
    ladder_rung: int
    reported_value: str
    location: str = Field(description="Page and table/figure it appears in.")
    quote: str


class Inventory(BaseModel):
    """Pass 1 — read the whole paper and enumerate before judging anything."""

    coverage: Coverage
    academic_variables: List[str] = Field(
        description="Every academic-functioning variable measured."
    )
    rejected_outcomes: List[RejectedOutcome]
    sc_measure_summary: str
    total_sc_reported: bool = Field(
        description=(
            "True if the paper reports a total self-compassion score. Determines whether "
            "subscale-level effects may be extracted at all."
        )
    )
    candidate_effects: List[CandidateEffect] = Field(
        description="EVERY self-compassion x academic effect found, before ladder filtering."
    )
    notes: str


# ──────────────────────────────── pass 2 ────────────────────────────────


class ExtractionRecord(BaseModel):
    """Pass 2 — the reviewable record, one per study."""

    identification: Identification
    methods: Methods
    population: Population
    sc_measure: SelfCompassionMeasure
    outcomes: List[Outcome]
    rejected_outcomes: List[RejectedOutcome]
    dropped_effects: List[DroppedEffect]
    flags: List[Flag]
    coverage: Coverage


# Domain order matches the Covidence rail, so the review UI can be transcribed
# straight down into the form.
DOMAIN_ORDER = [
    ("identification", "Identification"),
    ("methods", "Methods"),
    ("population", "Population"),
    ("sc_measure", "Interventions"),
]

FIELD_LABELS = {
    "title": "Title",
    "citation": "Citation (APA7 in-text)",
    "year": "Publication year",
    "country": "Country",
    "article_type": "Article type",
    "aim": "Aim / research question",
    "design_type": "Design type",
    "n_timepoints": "Number of timepoints",
    "intervention_type": "Intervention type",
    "intervention_duration": "Intervention duration",
    "n_study": "N (study-level)",
    "student_type": "Student type",
    "age_mean": "Age (mean)",
    "age_sd": "Age (SD)",
    "age_range": "Age (range)",
    "pct_female": "% female",
    "sample_specification": "Sample specification",
    "sampling_method": "Sampling method",
    "measure_format": "Measure format and item count",
    "measure_version": "Measure version",
    "total_score_used": "Total score used?",
    "subscales_reported": "Subscales with effects reported?",
    "scs_reporting": "SCS reporting",
    "scs_valence": "SCS valence",
    "scoring": "Scoring",
    "academic_variable_name": "Academic variable name",
    "outcome_name_coded": "Outcome name coded",
    "table_name": "Table name",
    "measure_used": "Measure used",
    "measure_description": "Measure description",
    "outcome_reporting": "Outcome reporting",
    "adaptations": "Adaptations",
    "af_valence": "AF valence",
    "outcome_notes": "Outcome notes",
    "variables": "Variables in effect",
    "effect_type": "Effect type and statistic",
    "effect_value": "Effect value (raw)",
    "p_value": "p",
    "effect_direction": "Effect direction",
    "effect_significance": "Effect significance",
    "n_effect": "n (effect-level)",
    "notes_adjusted": "Notes 1 (adjusted vs unadjusted)",
    "notes_design": "Notes 2 (design)",
    "narrative_summary": "Narrative summary",
    "t_value": "t value",
    "df_numerator": "df (numerator)",
    "df_denominator": "df (denominator)",
    "f_value": "F value",
    "cohens_d": "Cohen's d",
    "mean_group1": "Mean group1/time1",
    "mean_group2": "Mean group2/time2",
    "sd_group1": "SD group1/time1",
    "sd_group2": "SD group2/time2",
}
