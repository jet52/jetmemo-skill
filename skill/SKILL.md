---
name: jetmemo
description: 'Generate bench memos for the North Dakota Supreme Court from appellate case PDFs. Use when the user provides case documents (briefs, notices of appeal, orders) and asks to draft a bench memo, generate a bench memo, prepare a case summary, or analyze an appeal. Triggers: bench memo, jetmemo, jet memo, draft memo, generate memo, case analysis, prepare memo, analyze appeal, memo for oral argument.'
---

# Bench Memo Generator

Generate bench memos for ND Supreme Court oral arguments from appellate case PDFs. Uses a three-phase pipeline — Preparation, Parallel Analysis, Synthesis — to delegate focused analysis to subagents and minimize token usage in the main context.

## Fixed Paths

| Resource               | Path                                                      |
| ---------------------- | --------------------------------------------------------- |
| This skill             | `~/.claude/skills/jetmemo/`                            |
| ND opinions (markdown) | `~/refs/opin/markdown/`                                    |
| ND Century Code        | `~/refs/ndcc/`                                             |
| ND Admin Code          | `~/refs/ndac/`                                             |
| ND Court Rules         | `~/refs/rule/`                                             |
| Style reference        | `~/.claude/skills/jetmemo/references/style-spec.md`    |
| Memo format reference  | `~/.claude/skills/jetmemo/references/memo-format.md`   |
| Citation checker       | `~/.claude/skills/jetmemo/scripts/verify_citations.py` |
| splitmarks             | `~/.claude/skills/jetmemo/scripts/splitmarks.py`       |

> **Dependencies:**
> - splitmarks.py requires `pypdf` (`pip install pypdf`)
> - verify_citations.py requires `jetcite` — install as a Claude skill from [github.com/jet52/jetcite](https://github.com/jet52/jetcite) or via `pip install git+https://github.com/jet52/jetcite.git`

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

**ND Court Rules** — `~/refs/rule/<category>/rule-<number>.md`. Categories map from citation abbreviations:

| Citation prefix | Directory |
| --------------- | --------- |
| N.D.R.App.P. | `ndrappp/` |
| N.D.R.Civ.P. | `ndrcivp/` |
| N.D.R.Crim.P. | `ndrcrimp/` |
| N.D.R.Ev. | `ndrev/` |
| N.D.R.Ct. | `ndrct/` |
| N.D.R.Juv.P. | `ndrjuvp/` |
| N.D.Sup.Ct.Admin.R. | `ndsupctadminr/` |
| N.D.R.Prof.Conduct | `ndrprofconduct/` |
| N.D.Code.Jud.Conduct | `ndcodejudconduct/` |

Example: N.D.R.Civ.P. 12(b) → `~/refs/rule/ndrcivp/rule-12.md`. N.D.R.App.P. 35.1 → `~/refs/rule/ndrappp/rule-35.1.md`. The parenthetical (e.g., `(b)`) refers to a subsection within the rule file — read the whole file and search for the subsection.

**READ-ONLY access to `~/refs/` is pre-authorized.** All agents (including subagents) may read files from this directory without additional permission. Never modify, delete, or write to any file in this directory.

---

## Phase 1: Preparation (Orchestrator, Sequential)

### Step 0: Scan, Classify, and Split

**Update check:** Run `python3 ~/.claude/skills/jetmemo/scripts/check_update.py` silently. If it prints output, include it as a note to the user.

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
   python ~/.claude/skills/jetmemo/scripts/splitmarks.py record.pdf --dry-run -vv   # preview bookmark tree
   python ~/.claude/skills/jetmemo/scripts/splitmarks.py record.pdf -o .split_records --no-clobber -v  # first pass
   ```

   After the first pass, check if any output file is still large (>30 pages) and has sub-bookmarks. If so, run `splitmarks` again on that file:

   ```bash
   python ~/.claude/skills/jetmemo/scripts/splitmarks.py .split_records/R.Cited.pdf --dry-run -vv   # check for sub-bookmarks
   python ~/.claude/skills/jetmemo/scripts/splitmarks.py .split_records/R.Cited.pdf -o .split_records/cited --no-clobber -v  # split again
   ```

   Repeat until every output file is a single record item or has no further bookmarks. Then classify all resulting split files the same way.

4. If **no PDFs** found, ask the user. If many files or ambiguous, confirm with the user.

5. **Build a manifest:** `{path, type, page_count}` for every document. Track this manifest for all subsequent steps.

6. **Recommendation mode:** Scan the user's request for trigger keywords: "with recommendation(s)", "recommend", or "take a position." If found, set `recommend_mode: true`. Otherwise, `recommend_mode: false` (default). This flag controls whether the memo includes a recommended disposition for each issue.

### Step 1: Read References and Extract Text

1. **Read references** into main context (small files, needed for synthesis):
   - `~/.claude/skills/jetmemo/references/style-spec.md`
   - `~/.claude/skills/jetmemo/references/memo-format.md`

2. **Extract text** from all PDFs using the smart extraction script, which tries multiple PDF libraries in priority order and picks the best result:

   ```bash
   python3 ~/.claude/skills/jetmemo/scripts/extract_text.py <file1>.pdf <file2>.pdf ...
   ```

   The script tries extractors in this order: `pdftotext` (Poppler) → `pypdf` → `PyMuPDF` → `pdfplumber` → `marker`. Each page is scored individually. It stops as soon as one extractor produces good output (≥ 70% of text-bearing pages score ≥ 5 words/line). If only marginal output is found, it uses the best available. The script writes two files per PDF:

   - `<file>.txt` — extracted text
   - `<file>.extraction.json` — per-page quality metadata including `visual_read_pages` (1-indexed page numbers that need visual read) and `visual_read_ranges` (compact string like `"31-40, 45"`)

   Exit codes:
   - **0:** usable text was extracted for all PDFs
   - **1:** one or more PDFs failed extraction entirely — mark those as `needs_visual_read: true` in the manifest

   When specific pages need visual read (listed in `.extraction.json`), the agent prompt **must** receive both the `.txt` path and the PDF path, with instructions: "Pages [ranges] had poor text extraction. Use the Read tool on the PDF directly for those pages."

4. **Extract citation list:** Run the citation checker on all `.txt` files to build a structured citation list. This determines which conditional agents to launch.

   ```bash
   cat *.txt | python3 ~/.claude/skills/jetmemo/scripts/verify_citations.py --refs-dir ~/refs --json > citations.json
   ```

   The output is a JSON array. Each entry has `cite_type`, `local_path`, `local_exists`, `url`, and `search_hint`. Use `cite_type` to determine which agents to launch:
   - Any `cite_type` in `nd_case`, `us_supreme_court`, `federal_reporter`, `state_case`, `state_neutral` → launch Agent D
   - Any `cite_type` in `ndcc`, `ndcc_chapter`, `ndac`, `nd_court_rule`, `nd_const` → launch Agent E

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
> 4-8 documents important for the court to consider in resolving issues on appeal -- with record citations and brief descriptions.
>
> **5. Exhibit & Key Evidence Index**
> For each key piece of evidence (including exhibits, transcript testimony, etc) referenced:
> - Exhibit identifier and record citation (pinpoint page)
> - What the appellant/petitioner claims it proves
> - Short identifying quote (≤ 25 words) from the brief where it is discussed
>
> **6. Statutory Interpretation**
> If any issue involves interpretation of constitution, code, or other legal text (including contract, will, jury instruction, etc):
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
> If any issue involves interpretation of constitution, code, or other legal text:
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

**Launch only if** district court orders on appeal exist in the manifest.

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

**Reads:** transcript text or PDF. If the transcript is marked `needs_visual_read`, pass the PDF path with instructions to use the Read tool on the PDF directly, reading page by page. Because this is slow, indicate this may delay analysis.

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

**Launch only if** `citations.json` contains entries with `cite_type` in `nd_case`, `us_supreme_court`, `federal_reporter`, `state_case`, or `state_neutral`.

**Reads:** local opinion markdown files (preferred), web sources via jetcite-provided URLs (fallback)

**Input:** Pass Agent D the filtered list of case citation entries from `citations.json` — all entries where `cite_type` is `nd_case`, `us_supreme_court`, `federal_reporter`, `state_case`, or `state_neutral`. Each entry includes `cite_type`, `local_path`, `local_exists`, `url`, and `search_hint`.

**Prompt template:**

> **Precedent Verification**
>
> You have a list of case citations extracted from appellate briefs, with pre-resolved local paths and URLs from the citation checker. For each citation, look up the opinion and extract relevant information.
>
> **Citation data format:** Each citation entry includes:
> - `cite_text` / `normalized`: the citation string
> - `cite_type`: one of `nd_case`, `us_supreme_court`, `federal_reporter`, `state_case`, `state_neutral`
> - `local_path` / `local_exists`: path in `~/refs/` and whether the file exists
> - `url`: source URL (ndcourts.gov, CourtListener, Justia, etc.)
> - `search_hint`: text to match within the file
>
> ---
>
> **Lookup strategy by citation type:**
>
> **ND cases (`nd_case`):**
>
> 1. **Local files (fastest, most complete):** If `local_exists` is `true`, use the Read tool on `local_path`. Paragraphs are marked `[¶N]`.
> 2. **ndcourts.gov (primary web fallback):** If `local_exists` is `false`, use WebFetch on the `url` from the citation data. If the direct URL fails, fall back to the search endpoint:
>    ```
>    https://www.ndcourts.gov/supreme-court/opinions?cit1=YYYY&citType=ND&cit2=NNN&pageSize=10&sortOrder=1
>    ```
>    The search page returns case name, citation, and **highlight text** — a syllabus-like summary of key holdings. Mark the source as "ndcourts.gov (highlight)".
> 3. **CourtListener search API (secondary web fallback):** Use WebFetch:
>    ```
>    https://www.courtlistener.com/api/rest/v4/search/?q=%22YYYY+ND+NNN%22&type=o
>    ```
>    Returns JSON (no auth required) with `caseName`, `neutralCite`, `syllabus`. Match on `neutralCite` exactly. Mark the source as "CourtListener (syllabus)".
>
> **U.S. Supreme Court (`us_supreme_court`):**
>
> 1. **Local files:** If `local_exists` is `true`, read from `local_path`.
> 2. **Justia / CourtListener:** Use WebFetch on the `url` field. The URL typically points to Justia (`supreme.justia.com`) or CourtListener. Mark the source as "Justia" or "CourtListener".
>
> **Federal reporters (`federal_reporter`) and state cases (`state_case`, `state_neutral`):**
>
> 1. **Local files:** If `local_exists` is `true`, read from `local_path`.
> 2. **CourtListener:** Use WebFetch on the `url` field. CourtListener redirect URLs (`courtlistener.com/c/...`) resolve to the opinion page. Mark the source as "CourtListener".
> 3. **CourtListener search API (if redirect URL fails):** Use WebFetch:
>    ```
>    https://www.courtlistener.com/api/rest/v4/search/?q=%22{search_hint}%22&type=o
>    ```
>    Returns JSON with `caseName`, `citation`, `syllabus`. Mark the source as "CourtListener (syllabus)".
>
> ---
>
> **Limitations of web fallbacks:** Web sources typically provide summary text (syllabus, headnotes), not full opinions. Pinpoint paragraph verification is not possible from web summaries.
>
> **Citations to verify:**
> [Insert citation entries from citations.json, plus the proposition each is cited for in the briefs]
>
> **Prioritization:** Focus on opinions cited for standards of review and contested holdings first. If the list exceeds 15 citations, skip string cites (citations grouped in a series without individual discussion). Prioritize ND cases (most relevant to this court's precedent), then U.S. Supreme Court cases, then federal and state cases.
>
> **For each citation:**
>
> 1. **Locate the opinion.** Use `local_path` if `local_exists`, then `url`, then CourtListener search. If none produces a result, mark as "Not found" and move on.
> 2. **Read the cited paragraph** (local: the pinpoint ¶, plus 1-2 surrounding paragraphs for context; web: use the syllabus and snippet). If no pinpoint and using local files, skim the full opinion.
> 3. **Extract the holding and key rule** from the cited paragraph(s) or syllabus.
> 4. **Assess support:** Does the cited paragraph (or syllabus) actually support the proposition it's cited for? Report: **Supports**, **Partially supports**, **Does not support**, or **Insufficient data** (when the web fallback syllabus is too sparse to assess).
> 5. **Standard of review:** If the opinion articulates a standard of review, note it.
>
> **Return two sections:**
>
> **A. Citation Verification Table:**
>
> | Citation | Type | Cited For | Source | Supports? | Holding/Key Rule | Standard of Review |
> | -------- | ---- | --------- | ------ | --------- | ---------------- | ------------------ |
>
> Source column values: "Local file", "ndcourts.gov (highlight)", "CourtListener", "CourtListener (syllabus)", "Justia", or "Not found".
>
> **B. Legal Framework Narrative:**
> For each issue area, write a brief narrative (2-4 sentences) summarizing the legal framework established by the cited cases. Group by issue.

### Agent E: Statutory, Administrative Code & Court Rule Verification (Conditional)

**Launch only if** `citations.json` contains entries with `cite_type` in `ndcc`, `ndcc_chapter`, `ndac`, `nd_court_rule`, or `nd_const`.

**Reads:** local markdown files from `~/refs/ndcc/`, `~/refs/ndac/`, and `~/refs/rule/`

**Input:** Pass Agent E the filtered list of statutory/regulatory/rule entries from `citations.json`. Each entry includes `local_path`, `local_exists`, `url`, and `search_hint`.

**Prompt template:**

> **Statutory, Administrative Code & Court Rule Verification**
>
> You have a list of N.D.C.C., N.D.A.C., N.D. Constitution, and/or court rule citations extracted from appellate briefs, with pre-resolved local paths and URLs from the citation checker. For each citation, look up the text and verify that it exists and supports the proposition it is cited for. Also verify the accuracy of any direct quotes from these sources.
>
> **Citation data format:** Each citation entry includes:
> - `cite_text` / `normalized`: the citation string
> - `cite_type`: `ndcc`, `ndcc_chapter`, `ndac`, `nd_court_rule`, or `nd_const`
> - `local_path` / `local_exists`: path in `~/refs/` and whether the file exists
> - `url`: official source URL (ndlegis.gov, ndcourts.gov, etc.)
> - `search_hint`: text to search for within the local file (e.g., `14-07.1-02`)
>
> **Lookup order:**
>
> 1. **Local files (fastest):** If `local_exists` is `true`, use the Read tool on `local_path`. Search for the `search_hint` value within the file to find the specific section. Sections appear as `### §` headings within chapter files. For court rules, search for the subsection (e.g., `(b)`) within the rule file.
>
> 2. **Web fallback:** If `local_exists` is `false`, use WebFetch on the `url` from the citation data.
>
> **Citations to verify:**
> [Insert citation entries from citations.json, plus the proposition each is cited for and any quoted language from the briefs]
>
> **For each citation:**
>
> 1. **Locate the section.** Use `local_path` if `local_exists`, otherwise WebFetch the `url`. If neither works, mark as "Not found" and move on.
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

2. **Exhibit Cross-Reference:** Merge lists of key evidence from Agents A and B. For each exhibit or record item, show what each side claims it proves. Flag exhibits cited by only one side.

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

### Step 7: Generate Word Document

Convert the markdown memo to a formatted .docx file matching the Court's bench memo template (QTPalatine 13pt, justified, 1.2 line spacing):

```bash
python3 ~/.claude/skills/jetmemo/scripts/memo_to_docx.py {memo_file}
```

This produces `{case_number}_memo.docx` alongside the markdown file. The docx uses the same styles as the Court's bench memos: Title, Address Block (with tab-aligned metadata), Heading 1 (centered section heads), Heading 2 (issue headings), Heading 3 (sub-arguments), and Main Body Text. Page numbers appear in the footer.

If python-docx is not installed, the script will print an error. Install with `pip install python-docx`.

### Step 8: Citation Verification (Optional)

If the user requests verification (or if you want to flag potential issues), run the citation checker on the finished memo:

```bash
python3 ~/.claude/skills/jetmemo/scripts/verify_citations.py --file {memo_file} --refs-dir ~/refs
```

The human-readable output shows total citations found, how many resolve locally vs. web-only vs. unresolved, grouped by type.

For JSON output (to inspect individual citations), add `--json`.

After verification, append a summary to the memo:

```
## CITATION VERIFICATION

Verified: X | Unverified: Y | Skipped: Z

### Unverified Citations
- [list any citations that could not be confirmed]
```

Record citations (R##) reference the appellate record and are not checked by the script.

---

## Token Efficiency

| Content           | Strategy                                  | Rationale                            |
| ----------------- | ----------------------------------------- | ------------------------------------ |
| Briefs (30-50pp)  | `extract_text.py` -> `.txt`, agent reads text | ~50% token savings vs multimodal PDF |
| Large record PDFs | `splitmarks` first, then extract per-file | Agents load only relevant documents  |
| Scanned PDFs      | Agent uses `Read` on PDF directly         | Fallback when text extraction fails  |
| ND opinions       | Agent reads `.md` directly                | Already markdown, very efficient     |
| N.D.C.C. / N.D.A.C. | Agent reads local `.md`, web fallback  | Local is fastest; web if ~/refs absent |
| Court Rules        | Agent reads local `.md`, web fallback  | Local is fastest; web if ~/refs absent |
| Reference files   | Orchestrator reads directly               | Small, needed for synthesis          |

## Fallback Handling

- If a subagent fails or times out: orchestrator reads the document directly in main context and performs that analysis step itself
- If `extract_text.py` exits with code 1 for a PDF (all extractors produced poor quality): mark `needs_visual_read` and pass the PDF path to the subagent with explicit instructions to use the Read tool on the PDF directly
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
