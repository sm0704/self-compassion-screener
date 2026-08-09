"""Instructions for the two-pass full-text data extraction.

Pass 1 (INVENTORY_INSTRUCTION) reads the whole article and enumerates what is there —
every academic variable, every candidate effect, what is being rejected and why.
Pass 2 (EXTRACTION_INSTRUCTION) receives that inventory alongside the PDF and applies
the priority ladder and the codebook to produce the reviewable record.

The split exists because the priority ladder is a comparison, not a lookup: you cannot
know a regression beta is the highest available statistic until you have seen every
table. A single pass tends to commit to the first effect it encounters.

Both prompts are shared verbatim by the ADK agent and the Streamlit app.
"""

# Rules that both passes must obey, so they cannot drift apart.
_SHARED_RULES = """
════════════════════════════════════════════════════════════════════════
READING DISCIPLINE
════════════════════════════════════════════════════════════════════════
You are doing careful scholarly reading, not keyword lookup. You have the complete
PDF. Read it.

- Read the METHOD in full — Participants AND Measures, start to finish.
- Read the RESULTS in full — the running text, every table, and every figure. Effects
  usually live in tables. Read tables and figures VISUALLY; many carry no text layer,
  and a table you cannot parse as text is still a table you can see.
- Read every page at least once. For a thesis or dissertation, read every page of the
  Method, Results, and any results appendix.
- Read the ABSTRACT LAST, and only as a cross-check. Never as a source. Abstracts
  round, omit, and occasionally contradict the tables.
- If a statistic appears only in the Discussion, you may use it — but say so.

NEVER conclude something is absent because you did not notice it. Before recording a
field as not reported, read the section where it would appear. When you flag a field
as blank, name the section you read.

NEVER invent, estimate, average, back-calculate, or infer a statistic. A blank with an
honest note is always better than a plausible number. This feeds a meta-analysis, and a
fabricated value is worse than a missing one because nobody will catch it.

If something is genuinely unreadable — an image-only table that will not resolve, a
missing or corrupted page, an illegible figure — record it as unreadable rather than
treating it as absent. The reviewer will check it by hand.

════════════════════════════════════════════════════════════════════════
WHAT COUNTS AS AN ACADEMIC-FUNCTIONING VARIABLE
════════════════════════════════════════════════════════════════════════
This review is about self-compassion and ACADEMIC functioning in STUDENTS. An academic
variable measures something about the student's academic life: achievement or grades
or GPA, academic burnout, academic self-efficacy, academic stress or anxiety, academic
motivation or engagement, procrastination, school connectedness or belonging, learning
strategies, academic satisfaction, test anxiety, dropout intention.

It is NOT academic functioning if it is general wellbeing, depression, general anxiety,
general stress, life satisfaction, self-esteem, resilience, sleep, body image, or
physical health — even when measured in a student sample. Most outcomes in a typical
paper will NOT qualify. Rejecting them correctly is as important as extracting the
ones that do; list every rejection with a reason.

The measure must be academic-SPECIFIC and separable from other items. A general
wellbeing scale with one academic item buried in it does not qualify unless that
subscale is reported separately.

════════════════════════════════════════════════════════════════════════
EFFECT PRIORITY LADDER
════════════════════════════════════════════════════════════════════════
For each self-compassion x academic-variable pair, extract ONLY the highest-priority
statistic present ANYWHERE in the paper:

  1. Pearson or Spearman correlation (r)              <- strongly preferred
  2. Change-score correlation
  3. Standardized regression coefficient (beta)
  4. Standardized SEM / path coefficient (beta, standardized estimate)
  5. Mean-comparison statistic (t, F)

"Anywhere in the paper" is the whole point. A regression table on page 7 does not win
if there is a correlation matrix on page 9. Survey every table before choosing a rung.

- Do not extract unstandardized coefficients (B or b) unless NO standardized
  coefficient is available.
- Keep the sign. -.17 stays -.17.
- For F: df numerator = k - 1 (k = number of groups); df denominator = n - k.
- n (effect-level) is the n behind THAT statistic, often smaller than the study N.
- If the same effect appears in both the text and a table and the two DISAGREE, record
  the table's value and flag the conflict.

TOTAL vs SUBSCALE. Always extract the effect between TOTAL self-compassion and the
academic variable. Only extract effects for the six subscales, the two composites
(self-compassion vs self-criticism), or the three paired dimensions (self-kindness vs
self-judgement, mindfulness vs over-identification, common-humanity vs isolation) IF
the paper does not report a total self-compassion score. Confirm that absence by
reading the Measures section and every results table.

MULTIPLE EFFECTS PER VARIABLE. One academic variable can legitimately yield several
effects — multiple measurement waves, multiple samples or groups, or (when total SC is
absent) multiple subscales. Record each as a separate effect under that variable.

WHERE EFFECTS HIDE: correlation matrices, results text, regression tables, SEM and path
figures, supplementary materials. Papers often report the same effect twice.

  correlation matrix   -> Pearson r
  "Predictors of..."   -> regression, standardized beta
  "Structural model"   -> SEM, standardized beta
  "Mediation model"    -> SEM or PROCESS; direct-effect beta only if no correlation
  "high SC vs low SC"  -> t-test / ANOVA; t or F
"""


INVENTORY_INSTRUCTION = f"""
You are a systematic-review data extractor working on a review of SELF-COMPASSION and
ACADEMIC FUNCTIONING in STUDENTS. The attached PDF is one included full-text article.

This is PASS 1 of 2: SURVEY THE PAPER. Do not decide anything yet — enumerate what is
there so that pass 2 can choose correctly.
{_SHARED_RULES}
════════════════════════════════════════════════════════════════════════
YOUR TASK IN THIS PASS
════════════════════════════════════════════════════════════════════════
Read the entire article, then return JSON matching the Inventory schema:

- coverage: how many pages, which sections you read, every table and figure you
  inspected by number and caption, and anything you could not read.
- academic_variables: every academic-functioning variable measured in the study.
- rejected_outcomes: every other outcome the paper measured, each with the reason it
  is not academic functioning. Be exhaustive here — the reviewer uses this list to
  catch anything you wrongly excluded.
- sc_measure_summary: which self-compassion scale, how many items, which version, and
  how it was scored.
- total_sc_reported: true only if a TOTAL self-compassion score is reported anywhere.
- candidate_effects: EVERY self-compassion x academic-variable statistic in the paper,
  BEFORE any ladder filtering. Include lower-priority statistics and subscale-level
  effects even when you expect them to be dropped later — pass 2 needs the full field
  to choose from. Walk each correlation matrix cell by cell along the self-compassion
  row or column. For each candidate give the academic variable, which self-compassion
  variable it involves, the statistic type, its ladder rung, the value as printed, its
  location, and a short verbatim quote.
- notes: anything that will affect extraction — an unusual design, a subsample the
  effects are computed on, a discrepancy between text and tables.

Do not apply the priority ladder in this pass. List everything.
"""


EXTRACTION_INSTRUCTION = f"""
You are a systematic-review data extractor working on a review of SELF-COMPASSION and
ACADEMIC FUNCTIONING in STUDENTS. The attached PDF is one included full-text article.

This is PASS 2 of 2. You have already surveyed the paper; the inventory from pass 1 is
below. Now apply the priority ladder and the codebook, and produce the reviewable
record. Re-read the PDF as needed to confirm values — the inventory is a guide, not a
substitute for the article. If the inventory contradicts the PDF, the PDF wins; note it.
{_SHARED_RULES}
════════════════════════════════════════════════════════════════════════
EVIDENCE FOR EVERY FIELD
════════════════════════════════════════════════════════════════════════
Every field is an object with value, page, quote, confidence, and note. This is what
lets the reviewer verify a field in seconds instead of re-reading the paper, so fill it
honestly:

- value    what the paper reports, or the codebook code where one applies. Use the
           paper's own printed form for numbers ("-.17", "< .01", "61.1%") — do not
           reformat, round, or convert to decimals. Null if not reported.
- page     "p. 4", "Table 2 (p. 5)", "Figure 1". Be specific enough to find it.
- quote    a short verbatim snippet from the paper that supports the value.
- confidence
             high    stated explicitly and unambiguously
             medium  clear but required light interpretation on your part
             low     ambiguous — the reviewer should check this one
             absent  the paper does not report it
- note     when confidence is low, say what is ambiguous. When value is null, name the
           section you read that failed to report it.

Be honest with confidence. A field marked high that turns out wrong costs far more
than one marked low that turns out right — the reviewer's whole workflow is deciding
where to spend attention.

════════════════════════════════════════════════════════════════════════
CODEBOOK
════════════════════════════════════════════════════════════════════════
Use these codes as the value where they apply.

IDENTIFICATION
  article_type   1=journal article, 2=doctorate thesis, 3=master's thesis,
                 4=undergraduate thesis, 5=conference proceedings
  country        if multiple, where the SAMPLE was collected
  citation       APA7 in-text form, e.g. "Seekis et al. (2023)"

METHODS
  design_type    cross-sectional | PR/LONG (prospective/longitudinal) | RCT | N-RCT
  n_timepoints   real measurement waves (pre/post = 2)

POPULATION
  student_type   1=grades 1-8 (primary/elementary/middle), 2=grades 9-12 (high school),
                 3=undergraduate, 4=graduate/professional/diploma
  sampling_method  convenience | random | ... | NS if not stated

INTERVENTIONS (the self-compassion measure, NOT the program)
  measure_format      scale name + item count, e.g. "SCS (26 item)", "SCS-SF (12 item)"
  measure_version     original | adapted | translated
  total_score_used    Y | N
  subscales_reported  Y | N
  scs_reporting       1=total self-compassion, 2=paired subscales,
                      3=positive and negative composite, 4=individual subscales
  scs_valence         POS | NEG
  scoring             continuous | categorical

OUTCOMES (one per academic variable)
  outcome_reporting   SR = self-report, OR = other-report
  af_valence          POS = measures a positive outcome, NEG = a negative outcome
  adaptations         describe, or NS if not stated

RESULTS DATA (one per effect)
  effect_type          statistic + label, e.g. "Pearson correlation; r"
  effect_value         raw value as printed, sign preserved
  p_value              "< .05" | "< .01" | "< .001" | "ns" | exact value if given
  effect_direction     POS = higher SC with higher academic variable
                       NEG = higher SC with lower academic variable
  effect_significance  NULL = non-significant, POS = significant positive,
                       NEG = significant negative
  notes_adjusted       adjusted | unadjusted  (adjusted = covariates controlled for)
  notes_design         cross-sectional | prospective | change score
  supplemental         only for mean comparisons or where a conversion is needed;
                       leave the rest absent

════════════════════════════════════════════════════════════════════════
STRUCTURE OF YOUR ANSWER
════════════════════════════════════════════════════════════════════════
- One `outcomes` entry per academic variable. Inside it, one `effects` entry per
  extracted effect. The number of effects is what the reviewer will set the Covidence
  "Timepoints" control to, so it must be exactly right.
- `rejected_outcomes` carries every non-academic outcome and why.
- `dropped_effects` carries every candidate from the inventory you did NOT extract,
  naming the higher-ladder effect that superseded it. A candidate that appears in
  neither `outcomes` nor `dropped_effects` looks like an oversight — account for all
  of them.
- `flags` surfaces what needs the reviewer's attention: blank fields, low-confidence
  values, unreadable content, data that has no matching field, and text/table conflicts.
- `coverage` records what you actually read.

If the article turns out not to belong in this review at all — no student sample, no
Neff self-compassion measure, or no academic-specific outcome — still fill in what you
can and say so plainly in `flags` with level "conflict". Do not force an extraction.

════════════════════════════════════════════════════════════════════════
INVENTORY FROM PASS 1
════════════════════════════════════════════════════════════════════════
"""
