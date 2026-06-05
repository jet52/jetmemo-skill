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
issues on appeal. If strength_mode (default), summarize each issue's strength
assessment with its confidence level (state no recommended disposition).
Otherwise, state the central question or tension.}

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

[¶last] {If strength_mode (default): Restate each issue's strength assessment
with its confidence level and the qualifications that bear on it. State no
recommended disposition. Otherwise: Summarize the key analytical considerations
for each issue without assessing which side is stronger.}
```

## Length (soft guideline)

- **Typical memo: 6–10 pages.** This is a target, not a hard cap.
- To reach it, **prune facts not necessary to understand and resolve the issues on appeal.** Reading every essential document in full (the Essential-Documents Rule) is required; *recounting* all of it is not. The BACKGROUND should carry only the facts the issues turn on.
- **Use judgment on analytical depth.** Simple cases stay short. Genuinely complex or multi-issue cases warrant more development — depth that the disposition actually needs, not depth for its own sake.
- **Over 15 pages must be justified** by multiple issues or particularly complicated issues. If a memo runs that long for any other reason, it is over-written — cut.
- Where a threshold ground disposes of an issue, it is appropriate to note that alternative grounds need not be reached rather than developing each at equal length.

**Page/word proxy (while drafting in markdown):** the bench-memo template (QTPalatine 13pt, 1.2 line spacing, justified) renders at *roughly* 350–450 words per page — so ~6–10 pages is approximately **2,500–4,000 words** of body text, and 15 pages is roughly **5,500–6,500 words**. Treat these as approximate; the rendered `.docx` page count (SKILL Step 8) is the authority. If unsure, render and check.

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

### Strength assessment (strength_mode, default)

When `strength_mode` is enabled (default):

- Assess which side has the stronger argument and whether it is more consistent with the text, precedent, and established interpretive principles
- State the assessment with explicit qualifications, hedging, and a confidence level (high / moderate / low); note what would change it and any reason the stronger argument may not carry the outcome
- Summarize the assessment in [¶1] and restate it in CONCLUSION
- **Never** state or imply a recommended disposition — do not write "The Court should affirm/reverse/remand" or that the Court should rule a particular way

When `strength_mode` is disabled (neutral mode):

- Do NOT assess which side is stronger
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
- When multiple district court cases are consolidated, prefix record cites with the district court case number per Rule 30(b)(1) — see style-spec.md
- Record citations must be hyperlinked — see style-spec.md for URL format
- Never use "para." or "paras." — always use ¶ / ¶¶
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
5. **Analysis** — strongest argument for the district court's ruling, then strongest counterargument, then assessment. If `strength_mode` (default), add the strength assessment with its confidence level; never a recommended disposition.

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
Then the strongest counterargument. Then assessment. If strength_mode (default),
state which side is stronger with a confidence level and qualifications;
never a recommended disposition.}
```

#### Interpretive Panel Section (Optional)

When the jetpanel skill produces a condensed panel analysis for a close interpretive question, insert it after the issue's Analysis paragraph and before the next issue heading:

```
[¶N+6] **Analysis:** {Analysis paragraph as usual.}

### Interpretive Panel: {Issue heading}

**Question:** {The close interpretive question}

**Panel Result:** {X-Y split or consensus, with methodology labels}

**Formalist Position (MANNING, BARNETT-SOLUM-THOMAS):** {1-3 sentences}

**Living Constitution / Pragmatist Position (STRAUSS, POSNER-BREYER):** {1-3 sentences}

**Natural Law Position (VERMEULE):** {1-3 sentences}

**Key Divergence:** {What methodological commitment produces the split}

**Strongest Arguments Each Way:**
- For {reading A}: {best argument with citation}
- For {reading B}: {best argument with citation}

## II. {Next Issue}
```

The panel section does not receive a paragraph number — it is a supplementary analysis block, not part of the sequential paragraph flow.

#### CONCLUSION

- 1-2 paragraphs maximum
- Restate the bottom line for each issue
- Bold the overall recommendation

### What to Avoid

- **Never** use placeholder brackets: [Date], [page], [County], etc.
- **Never** fabricate citations — verify every citation against an authoritative source. (This is not a briefs-only rule: the memo may cite relevant on-point authority the parties did not cite; verify it with extra care and flag it as the memo's addition.)
- **Never** use "I" or "we"
- **Never** omit record citations from BACKGROUND facts
- **Never** present only one side's arguments without the other
- **Never** use "para." or "paras." — always use the paragraph symbol ¶ (singular) or ¶¶ (plural)
