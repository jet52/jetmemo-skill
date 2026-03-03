---
name: bench-memo
description: 'Generate bench memos for the North Dakota Supreme Court from appellate case PDFs. Use when the user provides case documents (briefs, notices of appeal, orders) and asks to draft a bench memo, generate a bench memo, prepare a case summary, or analyze an appeal. Triggers: bench memo, draft memo, generate memo, case analysis, prepare memo, analyze appeal, memo for oral argument.'
---

# Bench Memo Generator

Generate bench memos for ND Supreme Court oral arguments from appellate case PDFs. Uses a three-phase pipeline — Preparation, Parallel Analysis, Synthesis — to delegate focused analysis to subagents and minimize token usage in the main context.

## Fixed Paths

| Resource               | Path                                                      |
| ---------------------- | --------------------------------------------------------- |
| This skill             | `~/.claude/skills/bench-memo/`                            |
| ND opinions (markdown) | `~/refs/opin/markdown/`                                    |
| ND Century Code        | `~/refs/ndcc/`                                             |
| ND Admin Code          | `~/refs/ndac/`                                             |
| Style reference        | `~/.claude/skills/bench-memo/references/style-spec.md`    |
| Memo format reference  | `~/.claude/skills/bench-memo/references/memo-format.md`   |
| Verification script    | `~/.claude/skills/bench-memo/scripts/verify_citations.py` |
| splitmarks             | `~/.claude/skills/bench-memo/scripts/splitmarks.py`       |

> **Dependency:** splitmarks.py requires `pypdf`. Install with `pip install pypdf`.

### ~/refs directory layout

All local reference material lives under `~/refs/`. This directory may or may not exist for a given user; always check before relying on it and fall back to web lookups when absent.

**ND opinions** — `~/refs/opin/markdown/<year>/<year>ND<number>.md` (e.g., `2022/2022ND210.md`). Paragraphs are marked `[¶N]`.

**ND Century Code (N.D.C.C.)** — `~/refs/ndcc/title-<T>/chapter-<T>-<CC>.md` where `<T>` is the title number and `<CC>` is the chapter number (with leading zero). Examples:
- N.D.C.C. § 14-07.1-01 → `~/refs/ndcc/title-14/chapter-14-07.1.md`
- N.D.C.C. § 12.1-02-02 → `~/refs/ndcc/title-12.1/chapter-12.1-02.md`

Each chapter file contains all sections in that chapter as `### § T-CC-SS` headings. To verify a specific section, read the chapter file and search for the section number.

**ND Administrative Code (N.D.A.C.)** — `~/refs/ndac/title-<T>/article-<T>-<AA>/chapter-<T>-<AA>-<CC>.md` where `<T>` is the title, `<AA>` is the article, and `<CC>` is the chapter. Some small articles are a single file: `~/refs/ndac/title-<T>/article-<T>-<AA>.md`. Examples:
- N.D.A.C. § 75-02-01.2-01 → `~/refs/ndac/title-75/article-75-02/chapter-75-02-01.2.md`
- N.D.A.C. § 75-07-01 → `~/refs/ndac/title-75/article-75-07.md` (single-file article)

Each chapter file contains all sections as `### § T-AA-CC-SS` headings.

**READ-ONLY access to `~/refs/` is pre-authorized.** All agents (including subagents) may read files from this directory without additional permission. Never modify, delete, or write to any file in this directory.

---

## Phase 1: Preparation (Orchestrator, Sequential)

### Step 0: Scan, Classify, and Split

1. **Scan** the working directory for `.pdf` files.

2. **Classify** each PDF — read just the first 2 pages (use the Read tool on the PDF) to determine document type:

   | Type               | Look for                                                            |
   | ------------------ | ------------------------------------------------------------------- |
   | `appellant-brief`  | "Brief of Appellant", filed by appellant's counsel                  |
   | `appellee-brief`   | "Brief of Appellee", "Brief of State", filed by appellee/respondent |
   | `reply-brief`      | "Reply Brief"                                                       |
   | `notice-of-appeal` | "Notice of Appeal"                                                  |
   | `order`            | District court order, judgment, findings                            |
   | `transcript`       | Hearing or trial transcript                                         |
   | `writ-petition`    | "Petition for Supervisory Writ", "Application for Writ", "Petition for Writ of Habeas Corpus" |
   | `writ-response`    | "Response to Petition", response filed by opposing party in writ proceeding |
   | `writ-reply`       | "Reply" filed by petitioner in writ proceeding                      |
   | `other`            | Anything else                                                       |

   > **Writ proceedings:** If the case is a writ proceeding, use "petitioner/respondent" terminology throughout instead of "appellant/appellee." Agent A handles the petition (or appellant brief), Agent B handles the response (or appellee brief).

3. **Split large PDFs down to individual record items.** For any PDF over ~30 pages that looks like a combined record or appendix, split recursively until each output file represents a single record item (e.g., R2, R7, R36):

   ```bash
   python ~/.claude/skills/bench-memo/scripts/splitmarks.py record.pdf --dry-run -vv   # preview bookmark tree
   python ~/.claude/skills/bench-memo/scripts/splitmarks.py record.pdf -o .split_records --no-clobber -v  # first pass
   ```

   After the first pass, check if any output file is still large (>30 pages) and has sub-bookmarks. If so, run `splitmarks` again on that file:

   ```bash
   python ~/.claude/skills/bench-memo/scripts/splitmarks.py .split_records/R.Cited.pdf --dry-run -vv   # check for sub-bookmarks
   python ~/.claude/skills/bench-memo/scripts/splitmarks.py .split_records/R.Cited.pdf -o .split_records/cited --no-clobber -v  # split again
   ```

   Repeat until every output file is a single record item or has no further bookmarks. Then classify all resulting split files the same way.

4. If **no PDFs** found, ask the user. If many files or ambiguous, confirm with the user.

5. **Build a manifest:** `{path, type, page_count}` for every document. Track this manifest for all subsequent steps.

6. **Recommendation mode:** Scan the user's request for trigger keywords: "with recommendation(s)", "recommend", or "take a position." If found, set `recommend_mode: true`. Otherwise, `recommend_mode: false` (default). This flag controls whether the memo includes a recommended disposition for each issue.

### Step 1: Read References and Extract Text

1. **Read references** into main context (small files, needed for synthesis):
   - `~/.claude/skills/bench-memo/references/style-spec.md`
   - `~/.claude/skills/bench-memo/references/memo-format.md`

2. **Extract text** from all PDFs using `pdftotext`:

   ```bash
   pdftotext <file>.pdf <file>.txt
   ```

3. **Quality check:** Mark a document as `needs_visual_read: true` in the manifest if **any** of these conditions are met:
   - The `.txt` file is nearly empty (< 100 characters) for a multi-page PDF
   - The average words per line is < 3 (indicates OCR degradation where individual words land on separate lines)
   - The text contains a high ratio of garbled characters or encoding artifacts

   Quick check for line-to-word ratio:

   ```bash
   awk '{words+=NF; lines++} END {if(lines>0) printf "%.1f words/line\n", words/lines}' file.txt
   ```

   When `needs_visual_read` is set, the agent prompt **must** receive the PDF path (not the `.txt` path) with explicit instructions: "Use the Read tool on this PDF directly, reading page by page."

4. **Extract citation list:** Grep all `.txt` files to build citation lists. These determine which conditional agents to launch.
   - **ND opinions:** `\d{4} ND \d+` patterns (e.g., `2022 ND 210`)
   - **N.D.C.C.:** `N\.D\.C\.C\. §\s*[\d.]+[-‑][\d.]+[-‑][\d.]+` patterns (e.g., `N.D.C.C. § 14-07.1-02`)
   - **N.D.A.C.:** `N\.D\.A\.C\. §\s*[\d.]+[-‑][\d.]+[-‑][\d.]+` patterns (e.g., `N.D.A.C. § 75-02-01.2-01`)

---

## Phase 2: Parallel Analysis (Subagents)

Launch all applicable agents **simultaneously** using the Task tool (`subagent_type: general-purpose`). Each agent gets:

- Paths to relevant `.txt` files (or PDF paths if `needs_visual_read`)
- Focused extraction instructions
- Expected output format (structured markdown)

### Agent A: Appellant Brief Analysis

**Reads:** appellant brief text, notice of appeal text, district court order text (if available)

**Prompt template:**

> **Appellant Brief Analysis**
>
> Read these files:
>
> - Appellant brief: `[path to .txt or .pdf]`
> - Notice of appeal: `[path]` (if available)
> - District court order: `[path]` (if available)
>
> Extract the following in structured markdown:
>
> **1. Case Metadata**
>
> - Case number (format: YYYYNNNN, e.g., 20250319)
> - Case name (Party v. Party)
> - Appellant name and counsel
> - Appellee name and counsel
> - Lower court (county, judge if available)
> - Procedural posture (what order is being appealed)
> - Oral argument date (if stated; "not specified" if unknown)
>
> **2. Issues on Appeal**
> For each issue, provide:
>
> - Issue heading (consolidate sub-arguments under the same legal theory as A, B, C)
> - Standard of review the appellant argues, with case citation
> - Each sub-argument with record citations
>
> **Issue consolidation rule:** If the appellant raises multiple sub-arguments under the same legal theory (e.g., multiple instances of ineffective assistance), group them as sub-points (A, B, C) under ONE issue. Each distinct legal theory or constitutional claim is its own issue.
>
> **3. Key Facts**
> Chronological list of key facts with record citations for every assertion.
>
> **4. Key Documents for Quick Reference**
> 4-8 important documents with record citations and brief descriptions.
>
> **5. Exhibit & Key Evidence Index**
> For each exhibit or key piece of evidence referenced:
> - Exhibit identifier and record citation (pinpoint page)
> - What the appellant/petitioner claims it proves
> - Short identifying quote (≤ 25 words) from the brief where it is discussed
>
> **6. Statutory Interpretation**
> If any issue involves interpreting a statute, rule, or regulation:
> - Which provision and the specific text at issue
> - What interpretation the appellant/petitioner advocates
> - Pinpoint cite to brief page where the argument appears
>
> **7. Preservation Flags**
> For each issue, note whether the brief identifies where the argument was raised below (objection, motion, etc.) with record citation. If the brief is silent on preservation, flag it.
>
> **Citation precision:** For every factual assertion, provide the record cite with pinpoint page (R##:page) and a short quote (≤ 15 words) identifying the relevant passage.
>
> Return only the structured extraction. Do not analyze or recommend.

### Agent B: Appellee Brief Analysis

**Reads:** appellee brief text

**Prompt template:**

> **Appellee Brief Analysis**
>
> Read: `[path to appellee brief .txt or .pdf]`
>
> Extract the following in structured markdown:
>
> **1. Metadata Corrections**
>
> - Appellee name and counsel
> - Any corrections to case metadata (case number, case name, procedural posture)
>
> **2. Responses to Issues**
> For each issue the appellee addresses:
>
> - Which appellant issue it responds to (note any reframing)
> - Standard of review the appellee argues (note any disagreements with appellant)
> - Arguments with record and case citations
> - Preservation/waiver arguments (if any — did appellant fail to raise issue below?)
>
> **3. Cross-Appeal Issues**
> If the appellee raises cross-appeal issues, extract them with the same structure as appellant issues.
>
> **4. Additional Facts**
> Any facts the appellee raises that the appellant omitted, with record citations.
>
> **5. Exhibit & Key Evidence Index**
> For each exhibit or key piece of evidence the appellee/respondent references:
> - Exhibit identifier and record citation (pinpoint page)
> - What the appellee/respondent claims it proves
> - Note if this exhibit was also cited by the other side (and for a different purpose)
>
> **6. Statutory Interpretation**
> If any issue involves statutory interpretation:
> - What interpretation the appellee/respondent advocates
> - Whether they agree on the text at issue or frame it differently
>
> **7. Procedural/Jurisdictional Arguments**
> - Arguments about appropriateness of review (mootness, standing, ripeness, jurisdiction)
> - Arguments that an issue was not preserved or was waived
> - Arguments that the appeal is untimely or procedurally defective
>
> **8. Factual Omissions**
> List significant facts from the appellant's brief that the appellee does NOT address or dispute. Also list facts the appellee emphasizes that the appellant omitted.
>
> **Citation precision:** For every factual assertion, provide the record cite with pinpoint page (R##:page) and a short quote (≤ 15 words) identifying the relevant passage.
>
> Return only the structured extraction. Do not analyze or recommend.

### Agent C1: Reply Brief (Conditional)

**Launch only if** a reply brief exists in the manifest.

**Reads:** reply brief text

**Prompt template:**

> **Reply Brief Analysis**
>
> Read: `[path to reply brief .txt or .pdf]`
>
> Extract the following in structured markdown:
>
> - **New arguments or authorities** not in the opening brief — for each, cite the reply brief page and note that it was not raised in the opening
> - **Concessions or abandoned points** — issues from the opening brief not defended in the reply
> - **Clarifications** of appellant's/petitioner's position
> - **New case citations** not in the opening brief
> - **Responses to preservation/waiver challenges** — does the reply address appellee's claim that an issue wasn't preserved?
>
> Return only the structured extraction. Do not analyze or recommend.

### Agent C2: District Court Orders (Conditional)

**Launch only if** district court orders exist in the manifest.

**Reads:** district court order text(s) — pass only the specific split record items (e.g., R7, R36, R37), not the full record PDF.

**Prompt template:**

> **District Court Order Analysis**
>
> Read these files:
>
> - `[path to each order .txt or .pdf]`
>
> Extract the following for each order:
>
> - Findings of fact (numbered list with citations)
> - Conclusions of law
> - Specific ruling being appealed
> - Judge's reasoning for the ruling
>
> Return only the structured extraction. Do not analyze or recommend.

### Agent C3: Hearing Transcript (Conditional)

**Launch only if** a transcript exists in the manifest.

**Reads:** transcript text or PDF. If the transcript is marked `needs_visual_read`, pass the PDF path with instructions to use the Read tool on the PDF directly, reading page by page.

**Prompt template:**

> **Hearing Transcript Analysis**
>
> Read: `[path to transcript .txt or .pdf]`
>
> [If needs_visual_read: "This transcript had poor text extraction. Use the Read tool on the PDF directly, reading page by page."]
>
> Extract the following in structured markdown:
>
> - Key testimony (witness, topic, substance) for each witness
> - Preservation of error: objections made or not made, judge's rulings on objections
> - Colloquy relevant to issues on appeal
> - Any admissions or concessions by either party
>
> Return only the structured extraction. Do not analyze or recommend.

### Agent D: Precedent Lookup (Conditional)

**Launch only if** ND citations were found in Step 1 **and** the opinions directory exists at `~/refs/opin/markdown/`.

**Reads:** local opinion markdown files

**Prompt template:**

> **ND Precedent Verification**
>
> You have a list of ND Supreme Court citations extracted from appellate briefs. For each citation, read the local opinion file and extract relevant information.
>
> **File location:** `~/refs/opin/markdown/`. Files are organized as `<year>/<year>ND<number>.md`. For example, `2022 ND 210` maps to `~/refs/opin/markdown/2022/2022ND210.md`. Paragraphs are marked `[¶N]`.
>
> **Citations to verify:**
> [Insert numbered list of citations with the proposition each is cited for]
>
> **Prioritization:** Focus on opinions cited for standards of review and contested holdings first. If the list exceeds 15 citations, skip string cites (citations grouped in a series without individual discussion).
>
> **For each citation:**
>
> 1. **Locate the file.** If the file does not exist, mark as "File not found" and move on.
> 2. **Read the cited paragraph** (the pinpoint ¶, plus 1-2 surrounding paragraphs for context). If no pinpoint, skim the full opinion.
> 3. **Extract the holding and key rule** from the cited paragraph(s).
> 4. **Assess support:** Does the cited paragraph actually support the proposition it's cited for? Report: **Supports**, **Partially supports**, or **Does not support**.
> 5. **Standard of review:** If the opinion articulates a standard of review, note it.
>
> **Return two sections:**
>
> **A. Citation Verification Table:**
>
> | Citation | Cited For | File Found | Supports? | Holding/Key Rule | Standard of Review |
> | -------- | --------- | ---------- | --------- | ---------------- | ------------------ |
>
> **B. Legal Framework Narrative:**
> For each issue area, write a brief narrative (2-4 sentences) summarizing the legal framework established by the cited cases. Group by issue.

### Agent E: Statutory & Administrative Code Verification (Conditional)

**Launch only if** N.D.C.C. or N.D.A.C. citations were found in Step 1.

**Reads:** local markdown files from `~/refs/ndcc/` and `~/refs/ndac/`

**Prompt template:**

> **Statutory & Administrative Code Verification**
>
> You have a list of N.D.C.C. and/or N.D.A.C. citations extracted from appellate briefs. For each citation, look up the section text and verify that it exists and supports the proposition it is cited for. Also verify the accuracy of any direct quotes from these sources.
>
> **Local file locations (check these first — fastest):**
>
> - **N.D.C.C.:** `~/refs/ndcc/title-<T>/chapter-<T>-<CC>.md` — where `<T>` is the title and `<CC>` is the chapter portion of the section number. For example, N.D.C.C. § 14-07.1-02 is in `~/refs/ndcc/title-14/chapter-14-07.1.md`. Sections appear as `### §` headings within the chapter file.
> - **N.D.A.C.:** `~/refs/ndac/title-<T>/article-<T>-<AA>/chapter-<T>-<AA>-<CC>.md` — where `<T>` is the title, `<AA>` is the article, and `<CC>` is the chapter. For example, N.D.A.C. § 75-02-01.2-01 is in `~/refs/ndac/title-75/article-75-02/chapter-75-02-01.2.md`. Some small articles are a single file: `~/refs/ndac/title-<T>/article-<T>-<AA>.md`.
>
> **Web fallback:** If `~/refs/ndcc/` or `~/refs/ndac/` does not exist, fall back to:
> - N.D.C.C.: WebFetch `https://www.ndlegis.gov/cencode/t{title}c{chapter}.html`
> - N.D.A.C.: WebFetch `https://www.ndlegis.gov/information/acdata/html/{title}-{article}-{chapter}.html`
>
> **Citations to verify:**
> [Insert numbered list of citations with the proposition each is cited for, and any quoted language from the briefs]
>
> **For each citation:**
>
> 1. **Locate the section.** Read the chapter file and search for the `### §` heading. If the file or section does not exist, mark as "Not found" and move on.
> 2. **Extract the relevant text** of the cited subsection.
> 3. **Assess support:** Does the section actually support the proposition it's cited for? Report: **Supports**, **Partially supports**, or **Does not support**.
> 4. **Quote verification:** If the brief quotes the statute or rule, compare the quoted text against the actual text. Report: **Accurate**, **Minor discrepancy** (with details), or **Inaccurate** (with details).
>
> **Return two sections:**
>
> **A. Statutory Verification Table:**
>
> | Citation | Cited For | Found | Supports? | Quote Accurate? | Actual Text (excerpt) |
> | -------- | --------- | ----- | --------- | --------------- | --------------------- |
>
> **B. Key Statutory Provisions:**
> For each issue area, list the controlling statutory or regulatory provisions with their relevant text excerpted.

---

## Phase 3: Synthesis (Orchestrator, Sequential)

### Step 2: Collect and Consolidate

**GATE: Do not begin synthesis until ALL launched agents have returned or timed out (5-minute timeout).** Use `TaskOutput` with `block: true` for each agent to wait for completion. If an agent exceeds the timeout, treat it as failed and apply fallback handling.

Collect results from all agents. Then:

- **Resolve metadata discrepancies** between Agent A and Agent B results (case number, names, procedural posture). If conflicts remain, note both versions and flag for user review.
- **Build master issue list** using the appellant's framing as the primary structure.
- **Map appellee's responses** to each appellant issue (from Agent B).
- **Merge** arguments, facts, and citations per issue from all agents.

**Comparative analysis** — using the merged agent results, build the following tables for use in the memo:

1. **Disputed vs. Undisputed Facts:** Cross-reference Agent A and Agent B fact lists. A fact is "undisputed" if both sides cite it or neither contests it. A fact is "disputed" if the parties offer conflicting accounts or one side challenges the other's characterization. For each disputed fact, note both versions with pinpoint cites.

2. **Exhibit Cross-Reference:** Merge exhibit lists from Agents A and B. For each exhibit, show what each side claims it proves. Flag exhibits cited by only one side.

3. **Preservation & Waiver:** For each issue, combine Agent A's preservation flags with Agent B's waiver arguments. Assess whether preservation appears adequate based on the record citations provided.

4. **First-Raised-on-Appeal:** Flag any argument that appears to lack a record citation for where it was raised below, or that the appellee claims was not preserved.

5. **Reply-Only Arguments:** From Agent C1, list arguments that appear in the reply but not in the opening brief. These may be improper new arguments — flag them.

**Fallback handling:** If any subagent fails or times out, read the relevant document(s) directly in main context and perform that analysis step here. If >50% of documents failed text extraction in Step 1, abandon the parallel approach entirely and fall back to sequential multimodal reads of the PDFs.

### Step 3: Legal Framing

For each consolidated issue:

1. **Determine correct standard of review** — adjudicate between the parties' positions using Agent D's precedent analysis (if available). If both sides cite the same standard, adopt it. If they disagree, assess which is correct based on the cited authorities.
2. **Identify the strongest argument supporting the district court's ruling** — articulate the best case for affirmance with specific citations.
3. **Identify the strongest counterargument** — the best case for the opposing position, with specific citations.
4. **Assess preservation** — if there's a waiver/preservation dispute, analyze it before reaching the merits.
5. **Flag statutory interpretation issues** — if the issue turns on statutory text, identify the interpretive question, the competing readings, and any relevant canons.
6. **If `recommend_mode` is enabled**, determine recommended disposition — affirm, reverse, or remand, with reasoning. If disabled, end the analysis after presenting both sides' strongest positions without stating a preferred outcome.

### Step 4: Generate the Memo

Write the complete bench memo in markdown per `memo-format.md`:

1. **Header** — case number, case name, oral argument date (omit if unknown), "Claude First Draft"
2. **Quick Reference** — 4-8 key documents with record citations (from Agent A)
3. **Opening [¶1]** — summarize the case and identify all issues. If `recommend_mode`, **bold the recommendation**. Otherwise, state the key tension or question the case presents.
4. **BACKGROUND** — factual and procedural history with record citations for every assertion
5. **Issue sections** — Roman numerals (I., II., III.), each with:
   - Standard of review with case authority
   - Appellant's arguments with citations
   - Appellee's arguments with citations
   - Sub-arguments (A, B, C) as needed
   - Analysis and assessment
6. **CONCLUSION** — If `recommend_mode`, restate recommendation in **bold**. Otherwise, summarize the key analytical considerations for each issue without stating a preferred outcome.

### Step 5: Self-Review

Review the memo against this checklist before presenting:

- [ ] All issues from Step 2 are addressed
- [ ] Paragraph numbering [¶1], [¶2], etc. is sequential throughout
- [ ] Every fact in BACKGROUND has a record citation
- [ ] Each issue section has a standard of review with case authority
- [ ] Both sides' arguments are fairly presented with citations
- [ ] Disputed facts are noted inline in BACKGROUND with both versions and cites
- [ ] Preservation is addressed for each issue (or noted as not at issue)
- [ ] Each issue analysis identifies the strongest argument for and against the district court
- [ ] Exhibit table included if ≥ 2 contested exhibits
- [ ] Writ terminology used correctly if writ proceeding
- [ ] If `recommend_mode`: recommendation appears in ¶1 (bold) and CONCLUSION (bold)
- [ ] If not `recommend_mode`: memo does NOT state a preferred disposition; analysis ends with both sides' positions
- [ ] No placeholder brackets like [Date], [page], [County]
- [ ] Only citations that appear in the parties' briefs are used
- [ ] Citation formats are correct (see style-spec.md)
- [ ] Record citations include pinpoint pages where available

Fix any issues found before presenting the memo to the user.

### Step 6: Write Output

Write the memo to a file in the current working directory:

- Default filename: `{case_number}_memo.md` (e.g., `20250319_memo.md`)
- If the user specifies a different output path, use that

### Step 7: Citation Verification (Optional)

If the user requests verification (or if you want to flag potential issues), verify citations using these sources in order:

#### ND Case Citations (YYYY ND ###)

1. **Local opinions** (fastest) — check if `~/refs/opin/markdown/{year}/{year}ND{number}.md` exists
2. **ND Courts website** — use WebFetch to search `https://www.ndcourts.gov/supreme-court/opinions?search={citation}`
3. **CourtListener** — if the user has a CourtListener API key, use the verification script

#### ND Century Code Citations (N.D.C.C. §)

1. **Local markdown** (fastest) — read `~/refs/ndcc/title-<T>/chapter-<T>-<CC>.md` and search for the `### §` heading
2. **ND Legislature** (fallback) — use WebFetch to check `https://www.ndlegis.gov/cencode/t{title}c{chapter}.html`

#### ND Administrative Code Citations (N.D.A.C. §)

1. **Local markdown** (fastest) — read `~/refs/ndac/title-<T>/article-<T>-<AA>/chapter-<T>-<AA>-<CC>.md` and search for the `### §` heading
2. **ND Legislature** (fallback) — use WebFetch to check `https://www.ndlegis.gov/information/acdata/html/{title}-{article}-{chapter}.html`

#### What to Skip

- Record citations (R##) — these reference the appellate record, not verifiable online
- Rule citations (N.D.R.App.P., N.D.R.Civ.P., N.D.R.Ev.) — procedural rules, skip

After verification, append a verification summary to the memo:

```
## CITATION VERIFICATION

Verified: X | Unverified: Y | Skipped: Z

### Unverified Citations
- [list any citations that could not be confirmed]
```

---

## Token Efficiency

| Content           | Strategy                                  | Rationale                            |
| ----------------- | ----------------------------------------- | ------------------------------------ |
| Briefs (30-50pp)  | `pdftotext` -> `.txt`, agent reads text   | ~50% token savings vs multimodal PDF |
| Large record PDFs | `splitmarks` first, then extract per-file | Agents load only relevant documents  |
| Scanned PDFs      | Agent uses `Read` on PDF directly         | Fallback when text extraction fails  |
| ND opinions       | Agent reads `.md` directly                | Already markdown, very efficient     |
| N.D.C.C. / N.D.A.C. | Agent reads local `.md`, web fallback  | Local is fastest; web if ~/refs absent |
| Reference files   | Orchestrator reads directly               | Small, needed for synthesis          |

## Fallback Handling

- If a subagent fails or times out: orchestrator reads the document directly in main context and performs that analysis step itself
- If `pdftotext` produces empty output or poor quality (avg < 3 words/line): mark `needs_visual_read` and pass the PDF path to the subagent with explicit instructions to use the Read tool on the PDF directly
- If `splitmarks` finds no bookmarks: document stays intact, processed as-is
- If `splitmarks` output still contains large multi-item files: process as-is, but note in the manifest that granular splitting was not possible
- If >50% of documents fail text extraction: abandon parallel approach, fall back to sequential multimodal reads

## Important Rules

- **Never fabricate citations.** Only cite cases and authorities that appear in the parties' briefs.
- **Never use placeholder brackets** like [Date], [page], [County]. If information is unavailable, omit it or write "not specified in the record."
- **Be neutral.** Present both sides fairly before offering analysis. If `recommend_mode`, recommendations should be clearly stated but appropriately hedged. If not, the memo should present the strongest arguments for each position and leave the disposition to the Court.
- **Record citations are mandatory** for every factual assertion in BACKGROUND.
- **Use "the Court"** when referring to the ND Supreme Court; **"the district court"** for the lower court.

## Writ Proceedings

When the case is a writ proceeding (petition for supervisory writ, habeas corpus, etc.):

- Use **petitioner/respondent** instead of appellant/appellee
- Agent A reads the petition; Agent B reads the response
- The opening paragraph should identify the type of writ and the relief sought
- Add a **threshold section** before the merits issues: whether the Court should exercise its supervisory jurisdiction (for supervisory writs) or whether the petition states a prima facie case (for habeas). This is Issue I in the memo.
- The "district court ruling" framing becomes "the ruling or action the petitioner seeks to challenge"
- Standard of review may differ — writs often involve questions of jurisdiction or authority, reviewed de novo
