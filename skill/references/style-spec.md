# Bench Memo Style Specification

## Citation Authority Hierarchy

When citation conventions conflict, apply the following priority order:

1. **North Dakota Court Rules** (N.D.R.App.P., N.D.R.Civ.P., etc.) — binding procedural requirements that govern practice before the Court; cannot be overridden
2. **Author/court preferences** — specific preferences defined in CLAUDE.md or communicated by the user; may override style guides but not court rules
3. **Garner's Redbook** — the ND Supreme Court's official style guide
4. **Bluebook** — default citation format for matters not addressed above

A North Dakota rule always overrides a conflicting Bluebook or Redbook convention. When in doubt, follow the North Dakota-specific format.

## Citation Formats

### ND Supreme Court Cases
```
2024 ND 156
2024 ND 156, ¶ 12
```
Always include pinpoint paragraph when citing a specific proposition.

### Reporter Citations
```
876 N.W.2d 234
```
Include when available alongside ND citation: `Case Name, 2024 ND 156, ¶ 12, 876 N.W.2d 234`

### Federal Cases
```
466 U.S. 668, 689 (1984)
```

### ND Statutes (Century Code)
```
N.D.C.C. § 14-09-06.2
N.D.C.C. § 14-09-06.2(1)(a)
```

### ND Court Rules
```
N.D.R.App.P. 35.1      (Appellate Procedure)
N.D.R.Civ.P. 12(b)     (Civil Procedure)
N.D.R.Ev. 401           (Evidence)
N.D.R.Crim.P. 29        (Criminal Procedure)
```

### Record Citations

**Single district court case:**
```
(R45)                    Record document 45
(R45:12)                 Record document 45, page 12
(R45:12:¶15)             Record document 45, page 12, paragraph 15
```

**Multiple district court cases (Rule 30(b)(1)):** When the appeal involves more than one district court case, each record citation must identify which case it belongs to. On first reference, use the full district court case number; on subsequent references, use only the last four digits:
```
First reference:         (00-0000-CV-00000 R55:22)
Subsequent references:   (0000 R55:22)
```

### Paragraph References

Always use the paragraph symbol (¶) — **never** write "para." or "paras." in any context.

**In record citations (N.D.R.App.P. 30)** — no space between ¶/¶¶ and the number:
```
(R45:12:¶15)
([R49:13](...), ¶38.)
¶¶7–14
```

**In case law citations (Bluebook)** — space between ¶/¶¶ and the number:
```
2024 ND 156, ¶ 12
¶¶ 6–8
```

This distinction arises because N.D.R.App.P. 30(b)(1) specifies the record citation format with no space (e.g., `(R156:12:¶3)`), which takes precedence over the Bluebook convention per the citation authority hierarchy above.

### Record Citation Hyperlinks

In markdown output, every record citation should be a hyperlink to `record.ndcourts.gov`. The URL format uses the district court case number (not the Supreme Court docket number):

```
https://record.ndcourts.gov/Case/{dc_docket}/{item}#page={page}
```

**Single district court case** (e.g., 00-0000-CV-00000):
```
[R899](https://record.ndcourts.gov/Case/00-0000-CV-00000/899)
[R899:2](https://record.ndcourts.gov/Case/00-0000-CV-00000/899#page=2)
[R899:2:¶5](https://record.ndcourts.gov/Case/00-0000-CV-00000/899#page=2)
```

When a citation contains multiple record items, hyperlink each separately:
```
([R240](https://record.ndcourts.gov/Case/00-0000-CV-00000/240); [R268](https://record.ndcourts.gov/Case/00-0000-CV-00000/268))
```

**Multiple district court cases (Rule 30(b)(1)):** When the appeal consolidates multiple district court cases, each record citation must identify which case it belongs to, and the URL must use that item's district court case number. On first reference, use the full district court case number; on subsequent references, use only the last four digits:
```
First:  [00-0000-CV-00000 R55:22](https://record.ndcourts.gov/Case/00-0000-CV-00000/55#page=22)
Later:  [0000 R55:22](https://record.ndcourts.gov/Case/00-0000-CV-00000/55#page=22)
```

### Authority Citation Hyperlinks

Citations to authority (case law, statutes, court rules, etc.) are hyperlinked automatically by the `link_citations.py` post-processing script using URLs from `citations.json`. The base citation text becomes the link text, with pinpoint references following outside the link:

```
[2024 ND 156](https://www.ndcourts.gov/...), ¶ 12
[N.D.C.C. § 14-09-06.2](https://ndlegis.gov/...)
[N.D.R.Civ.P. 56](https://www.ndcourts.gov/...)
```

Do not manually add authority citation links in the markdown — the script handles this.

## Citation Precision

All citations — case law, record, statutory — should be as precise as possible:

- **Record citations:** Always include pinpoint page when available: `(R45:12)` not just `(R45)`. Include paragraph when citing a specific finding: `(R45:12:¶15)`.
- **Case citations:** Always include pinpoint paragraph: `2024 ND 156, ¶ 12` not just `2024 ND 156`.
- **Short identifying quotes:** When a fact or holding could be ambiguous, include a short quote (≤ 15 words) to anchor the citation: `The district court found "no credible evidence of changed circumstances." (R36:4)`.
- **Brief page citations:** When attributing an argument to a party, cite the brief page: `Appellant argues the statute is ambiguous. (Ap't Br. at 14.)` Use the format `(Ap't Br. at ##)` or `(Ap'e Br. at ##)`.

## Tone and Voice

- **Neutral, analytical tone** throughout
- Present both sides fairly before offering assessment
- When `strength_mode` is enabled (default), the strength assessment should be clearly stated but appropriately hedged, with explicit qualifications and a confidence level (high / moderate / low), and never phrased as a recommended disposition
- When `strength_mode` is disabled (neutral mode), present both sides' strongest positions without assessing which is stronger
- Use **"the Court"** when referring to the ND Supreme Court
- Use **"the district court"** for the lower court
- Do not use "I" or "we" — write in the third person (e.g., "the stronger argument is...," "the appellant's reading fits the text better")
- Avoid legalese: no "herein," "wherefore," "aforementioned," "said" as a pronoun
- Active voice unless passive genuinely improves readability
- Use the Oxford comma
- In writ proceedings, use **"petitioner"** and **"respondent"** instead of "appellant" and "appellee"
- Use **"the petition"** and **"the response"** instead of "the opening brief" and "the appellee's brief" in writ proceedings

## Standards of Review

Common standards in ND appellate practice — use the one cited in the briefs:

| Standard | When Used | Key Language |
|----------|-----------|--------------|
| De novo | Questions of law, constitutional issues, statutory interpretation | "Freely reviewable on appeal" |
| Clearly erroneous | Findings of fact, sufficiency of evidence | "Definite and firm conviction a mistake has been made" |
| Abuse of discretion | Discretionary rulings (evidentiary, discovery, sentencing) | "Acted arbitrarily, unreasonably, or unconscionably" |
| Plain error | Unpreserved errors | "Obvious error affecting substantial rights" |

## Author Preferences

These override Redbook and Bluebook defaults per the citation authority hierarchy (item 2).

### Brief Citation Abbreviations

| Full Form | Abbreviation |
|-----------|-------------|
| Appellant's Brief | Ap't Br. |
| Appellee's Brief | Ap'e Br. |
| Reply Brief | Reply Br. |

Use these abbreviated forms in all parenthetical citations: `(Ap't Br. at 14.)`, `(Ap'e Br. at 7.)`. In running text, the full form may be used on first reference if needed for clarity.
