# Bench Memo Format

## Complete Structure

```markdown
# BENCH MEMO

**Case No. {case_number}**
**{Case Name}**
**Date of Oral Argument: {date}** ← omit entire line if unknown
**Claude {Opus 4.6}**

## Quick Reference

- **{Document Description}** ({record_cite}) - Brief explanation of significance
- **{Document Description}** ({record_cite}) - Brief explanation of significance
  [4-8 items total]

[¶1] {Opening paragraph: summarize the case in 2-3 sentences and identify all
issues on appeal. If recommend_mode, state the recommendation and **bold the
recommendation sentence.** Otherwise, state the central question or tension.}

## BACKGROUND

[¶2] {Factual history with record citations for every assertion.}

[¶3] {Procedural history with record citations.}

[¶N] {Continue as needed...}

## I. {First Issue Statement}

[¶N+1] {Standard of review with case authority from the briefs.}

[¶N+2] {Appellant's arguments with citations to briefs and record.}

### A. {Sub-argument if needed}

[¶N+3] {Appellant's argument on sub-point with citations.}

[¶N+4] {Appellee's response with citations.}

### B. {Next sub-argument}

[¶N+5] {Continue pattern...}

[¶N+6] {Analysis and assessment. Present both sides, then evaluate.}

## II. {Second Issue Statement}

[¶...] {Same structure: standard of review, arguments, analysis.}

## CONCLUSION

[¶last] {If recommend_mode: Restate recommendation. **Bold the recommendation
sentence.** Briefly summarize the key reasons. Otherwise: Summarize the key
analytical considerations for each issue without stating a preferred outcome.}
```

## Formatting Rules

### Paragraph Numbering

- Every paragraph is numbered: [¶1], [¶2], [¶3], etc.
- Numbering is **sequential throughout the entire memo** — do not restart at each section
- The opening paragraph is always [¶1]
- CONCLUSION contains the final paragraph number

### Headings

- Major sections in **ALL CAPS**: `## BACKGROUND`, `## CONCLUSION`
- Issue headings use **Roman numerals**: `## I.`, `## II.`, `## III.`
- Sub-arguments use **letters**: `### A.`, `### B.`, `### C.`

### Recommendations (recommend_mode only)

When `recommend_mode` is enabled:

- State recommendation in [¶1] — **bold** the sentence
- Restate recommendation in CONCLUSION — **bold** the sentence
- Use language like: "**The Court should affirm...**" or "**The Court should reverse...**"

When `recommend_mode` is disabled (default):

- Do NOT state a recommended disposition
- End analysis with both sides' strongest positions
- ¶1 should identify the central question, not a conclusion
- CONCLUSION should summarize the analytical framework, not a result

### Content Requirements

#### Quick Reference

- 4-8 key documents the justices should have at hand
- Each with record citation and brief description of significance

##### Exhibit Reference (when applicable)

If the case involves contested exhibits, add after Quick Reference:

```
## Key Exhibits

| Exhibit | Record Cite | Appellant's Claim | Appellee's Claim |
|---------|-------------|-------------------|------------------|
| Exhibit A | (R12:45) | Shows X | Shows Y |
```

Include only exhibits where the parties disagree about significance, or that are central to the disposition. Omit if fewer than 2 contested exhibits.

#### BACKGROUND

- Every factual assertion must have a record citation: (R##), (R##:page), (R##:page:¶para)
- Include both factual and procedural history
- Chronological order is typical

##### Disputed Facts

When Agent analysis reveals factual disputes, note them inline in BACKGROUND using this pattern:

```
[¶N] The parties dispute [topic]. Appellant contends [version] (R##:page), while
Appellee asserts [version] (R##:page). The district court found [resolution if any]
(R##:page).
```

Do not create a separate "disputed facts" section — weave the disputes into the narrative where they naturally arise.

#### Issue Sections

Each must include:

1. **Preservation** — whether the issue was preserved below, with record citation to the objection/motion. If disputed, note both sides' positions. If unpreserved, note the applicable standard (plain error, etc.). May be omitted when preservation is clearly not at issue (e.g., pure legal questions raised in dispositive motions).
2. **Standard of review** — with specific case authority from the briefs
3. **Appellant's arguments** — with citations to briefs and record
4. **Appellee's arguments** — with citations to briefs and record
5. **Analysis** — strongest argument for the district court's ruling, then strongest counterargument, then assessment. If `recommend_mode`, add recommendation.

Template:

```
## I. {Issue Statement}

[¶N] **Preservation:** {Whether this issue was preserved below, with record
citation to the objection/motion. If disputed, note both sides' positions.
If unpreserved, note the applicable standard (plain error, etc.).}

[¶N+1] **Standard of review:** {Standard with case authority.}

[¶N+2] {Appellant's arguments with citations to briefs and record.}

[¶N+3] {Appellee's arguments with citations to briefs and record.}

[¶N+4] **Analysis:** {Strongest argument for the district court's ruling.
Then the strongest counterargument. Then assessment. If recommend_mode,
state recommended disposition.}
```

#### CONCLUSION

- 1-2 paragraphs maximum
- Restate the bottom line for each issue
- Bold the overall recommendation

### What to Avoid

- **Never** use placeholder brackets: [Date], [page], [County], etc.
- **Never** fabricate citations — use only cases from the parties' briefs
- **Never** use "I" or "we"
- **Never** omit record citations from BACKGROUND facts
- **Never** present only one side's arguments without the other
