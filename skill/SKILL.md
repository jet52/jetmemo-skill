---
name: jetmemo
version: 3.8.2
description: 'Generate bench memos for the North Dakota Supreme Court from appellate case PDFs. Use when the user provides case documents (briefs, notices of appeal, orders) and asks to draft a bench memo, generate a bench memo, prepare a case summary, or analyze an appeal. Triggers: bench memo, jetmemo, jet memo, draft memo, generate memo, case analysis, prepare memo, analyze appeal, memo for oral argument.'
---

# Bench Memo Generator

Generate bench memos for ND Supreme Court oral arguments from appellate case PDFs. Uses a three-phase pipeline — Preparation, Parallel Analysis, Synthesis — to delegate focused analysis to subagents and minimize token usage in the main context.

## Fixed Paths

| Resource               | Path                                                      |
| ---------------------- | --------------------------------------------------------- |
| This skill             | `~/.claude/skills/jetmemo/`                            |
| Opinions               | `~/refs/opin/{reporter}/`                                     |
| Statutes               | `~/refs/statute/NDCC/`, `~/refs/statute/USC/`                 |
| Regulations            | `~/refs/reg/NDAC/`, `~/refs/reg/CFR/`                         |
| Court Rules            | `~/refs/rule/{set}/`                                          |
| Constitutions          | `~/refs/cnst/ND/`, `~/refs/cnst/US/`                          |
| Style reference        | `~/.claude/skills/jetmemo/references/style-spec.md`    |
| Memo format reference  | `~/.claude/skills/jetmemo/references/memo-format.md`   |
| Citation checker       | `~/.claude/skills/jetmemo/scripts/verify_citations.py` |
| splitmarks             | `~/.claude/skills/jetmemo/scripts/splitmarks.py`       |

> **Dependencies:**
> - splitmarks.py requires `pypdf` (`pip install pypdf`)
> - verify_citations.py uses a bundled copy of `jetcite` (in `lib/jetcite/`); to update, run `make vendor-jetcite` from the project root
> - `httpx` (ideally `httpx[socks]`) is optional: jetcite uses it to resolve/fetch source URLs, but imports and local `~/refs` citation scanning work without it. When httpx (or its `socksio` extra under a SOCKS proxy) is missing, network lookups degrade gracefully to search URLs — prefer MCP servers for retrieval in that case (see the **Legal-Research MCP Servers** section).

### ~/refs directory layout

All local reference material lives under `~/refs/`. This directory may or may not exist for a given user; always check before relying on it and fall back to web lookups when absent.

**Opinions** — `~/refs/opin/{reporter}/{volume or year}/{file}.md`. Examples:
- 2024 ND 156 → `~/refs/opin/ND/2024/2024ND156.md`. Paragraphs are marked `[¶N]`.
- 585 N.W.2d 123 → `~/refs/opin/NW2d/585/123.md`
- 505 U.S. 377 → `~/refs/opin/US/505/377.md`

**Statutes** — `~/refs/statute/{code}/...`. Examples:
- N.D.C.C. § 14-07.1-01 → `~/refs/statute/NDCC/title-14/chapter-14-07.1.md`
- N.D.C.C. § 12.1-02-02 → `~/refs/statute/NDCC/title-12.1/chapter-12.1-02.md`
- 42 U.S.C. § 1983 → `~/refs/statute/USC/42/1983.md`

Each NDCC chapter file contains all sections as `### § T-CC-SS` headings. To verify a specific section, read the chapter file and search for the section number.

**Regulations** — `~/refs/reg/{code}/...`. Examples:
- N.D.A.C. § 75-02-01.2-01 → `~/refs/reg/NDAC/title-75/article-75-02/chapter-75-02-01.2.md`
- 40 C.F.R. § 52.21 → `~/refs/reg/CFR/40/52.21.md`

**Constitutions** — `~/refs/cnst/{jurisdiction}/...`. Examples:
- N.D. Const. art. I, § 20 → `~/refs/cnst/ND/art-01/sec-20.md`
- U.S. Const. amend. XIV → `~/refs/cnst/US/amend-14.md`

**Court Rules** — `~/refs/rule/{set}/rule-{number}.md`. Examples:
- N.D.R.Civ.P. 12(b) → `~/refs/rule/ndrcivp/rule-12.md`
- Fed. R. Civ. P. 56 → `~/refs/rule/FRCP/rule-56.md`

The parenthetical (e.g., `(b)`) refers to a subsection within the rule file — read the whole file and search for the subsection.

**Read access to `~/refs/` is pre-authorized.** All agents (including subagents) may read files from this directory without additional permission. Do not modify or delete existing files. Adding new files is permitted only by jetcite's caching functions and scraper scripts.

---

## The Essential-Documents Rule (non-negotiable)

Some documents must be **read in full** before any analysis, regardless of length, scan quality, or token cost:

1. **Every order and judgment on appeal** — the dispositions under review. These are short and dispositive; there is never an excuse to work from the briefs' description of them.
2. **Every document on the memo's Quick Reference / key-documents and highly-relevant lists.** If a document is important enough to list for the justices, it is important enough to have been read.
3. The **relevant portions** of large supporting items (full transcript, full record) — read in part, but read; never assume their contents.

Token efficiency exists to make *thorough* reading affordable. Splitting, text extraction, and parallel agents are tools for reading the whole essential set cheaply — **never** a license to skip it. When efficiency and thoroughness conflict over an essential document, **thoroughness wins, every time.**

- **Never infer** the contents, reasoning, or grounds of an order, judgment, or key document from the parties' briefs. The briefs are advocacy; the order is the ruling.
- **Hedging is a symptom, not a style.** If you are about to write "the district court *appears to* have," "*seems to* have," or "*evidently*" about the lower court's reasoning, stop — that phrasing means you have not read the order. Read it, then state what it actually says with a pinpoint cite.
- **A missing essential document is a blocking condition, not a workaround.** If an order or judgment cannot be located in the provided materials, ask the user — do not proceed on inference. If a key document genuinely is not in what was provided, say so explicitly in the memo; never paper over the gap.

This rule governs the entire pipeline below; Steps 0, 2.5, and 5 enforce it.

---

## Phase 1: Preparation (Orchestrator, Sequential)

### Step 0: Scan, Classify, and Split

**Refs setup:** Run `python3 ~/.claude/skills/jetmemo/scripts/ensure_refs.py`. If it prints output, include it as a note to the user. This is a no-op when `~/refs` already exists (e.g., in Claude Code); in Cowork it detects a mounted `refs` folder and symlinks `~/refs` to it.

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

3. **Split large PDFs down to individual record items.**

   **First, check whether the records already arrived split.** The `record-fetch` tool splits packets into per-document files by default, named `R{idx} - {DocumentName}.pdf` (e.g., `R38 - Order.pdf`). If the working directory already contains a set of such per-document files (filenames beginning with `R` followed by a number), the record is **already split** — skip splitmarks for those and classify them directly. Splitting is only a fallback for records that arrive as an un-split combined PDF (e.g., a clerk-emailed packet or a brief's appendix).

   For any PDF over ~30 pages that looks like a combined record or appendix, split recursively until each output file represents a single record item (e.g., R2, R7, R36):

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

   **Locate the dispositions on review (mandatory — per the Essential-Documents Rule).** The order(s) and judgment(s) being appealed must be found and isolated, even when buried in a large scanned record batch. Do not stop at "no order in the manifest":
   - Identify the order's/judgment's **record number and date** from the notice of appeal and the briefs' record citations (e.g., "R38").
   - **Read the record index** (usually the first record item) to map that record number to its page range in the combined batch.
   - Split with `splitmarks` to isolate it; if the batch has no bookmarks, target that specific page range.
   - **If the item is image-scanned and text extraction is thin, perform a visual read** (Read tool on the PDF pages directly) — this is mandatory, not "if time permits." Mark it `needs_visual_read` and ensure an agent actually reads it.

4. If **no PDFs** found, ask the user. If many files or ambiguous, confirm with the user.

5. **Build a manifest:** `{path, type, page_count, essential, read_status}` for every document. Track this manifest for all subsequent steps. Set `essential: true` for every order and judgment on appeal (and add other documents to the essential set in Step 2.5 once the key-documents list exists). Initialize `read_status: unread`; an agent flips it to `read` only after it has actually read the document's text (or visually read its pages). The Step 2.5 gate checks this field.

6. **Strength assessment mode:** Default `strength_mode: true`. Scan the user's request for suppression keywords: "neutral", "no assessment", "both sides only", "without assessment", or "no strength assessment." If found, set `strength_mode: false`. **Do not ask the user which mode they want.** When the request contains no suppression keyword, proceed directly with the strength assessment without prompting. When `strength_mode` is enabled, the memo assesses, for each issue, which side has the stronger argument and how well each position fits the text, precedent, and established interpretive principles — stated with appropriate qualifications, hedging, and an explicit confidence level (high / moderate / low), and **never** as a recommended disposition. When suppressed, the memo presents both sides' strongest positions without assessing which is stronger. In either mode, if there are close questions the memo may include suggested questions for oral argument designed to press counsel on the central strength or weakness of a position.

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

   The output is a JSON array. Each entry has `cite_type`, `jurisdiction`, `local_path`, `local_exists`, `url`, and `search_hint`. Case entries also carry `antecedent_name` (the case name preceding the cite — a heuristic, may be `null`) and, for parallel citations, `parallel_cite`, `redundant_parallel`, and `primary_cite` (entries marked `redundant_parallel: true` are a parallel form of `primary_cite` — the same case). Use `cite_type` to determine which agents to launch:
   - Any `cite_type` in `neutral_cite`, `us_supreme_court`, `federal_reporter`, `regional_reporter` → launch Agent D
   - Any `cite_type` in `statute`, `statute_chapter`, `regulation`, `court_rule`, `constitution` → launch Agent E

   **Pin-cite entries.** Entries with `cite_type: "pin_cite"` are Bluebook short forms from the briefs (`491 F.3d at 363`, `Goss at 365`, `Niemeyer, ¶ 12`, `Id. ¶ 15`) back-referencing an earlier full citation. They carry `parent_normalized` (the full cite they point to), `pin_page` or `pin_paragraph`, and — when resolved — `parent_local_path`/`parent_local_exists` (pins have no refs file of their own; read the parent's). Pass resolved pin entries to Agent D alongside their parents so the pin page/paragraph can be checked against the parent opinion. Entries with a `pin_warning` field are **unresolved short forms** (no earlier full cite matches — e.g. a transposed volume number, or an `Id.` after an ambiguous string cite): treat each as a likely citation defect in the brief and note it in the memo's citation-check section. Pin entries never launch Agent E and are never cached.

---

## Legal-Research MCP Servers (ndcourts-mcp, CourtListener)

Two optional MCP servers improve case-law lookup and verification when connected. **They are augmentation, not replacement** — every check degrades gracefully to the existing pipeline (`~/refs/` local files → `WebFetch` on the citation's `url` → CourtListener search API). Never fail or stall a memo because an MCP server is absent or returns no data.

**Availability:** Before relying on a server, check whether its tools are present in your tool set — an ndcourts-mcp tool such as `mcp__ndcourts__verify_citation`, or a CourtListener tool such as `mcp__claude_ai_CourtListener__search`. If a tool is not present, skip silently to the next tier.

**Source precedence — apply at every case-citation lookup or verification; fall through on a miss:**

1. **ndcourts-mcp** (primary, North Dakota cases) — a local ND opinion corpus. Deterministic, no network or proxy, so it works in sandboxes (e.g. Cowork) where outbound HTTP is restricted.
2. **CourtListener MCP** (secondary) — case data ndcourts-mcp lacks: U.S. Supreme Court, federal, and other-state authorities, and ND opinions missing from the ND corpus.
3. **Existing pipeline** (fallback) — `~/refs/` local files, then `WebFetch` on the `url` from `citations.json`, then the CourtListener search API. The only path when no MCP server is connected.

A local `~/refs/` opinion file, when present, is equally authoritative and instant; use it or the MCP — whichever is available — before any web fetch. **Never go to the web for an ND case citation without first trying ndcourts-mcp or a local file.**

**Out of scope for both servers:** the authoritative text of statutes, court rules, the constitution, and the administrative code — these always resolve through the existing pipeline (Agent E / `~/refs/` / web). ndcourts-mcp covers ND *opinions* only.

**ndcourts-mcp tools (call by full `mcp__ndcourts__` name):**

- `lookup_opinion(citation, include_text=False, text_limit=5000)` → metadata and all known parallel citations for a cite; set `include_text=True` for the first `text_limit` characters.
- `get_opinion_text(citation, offset=0, limit=10000)` → opinion text in chunks; paginate by advancing `offset` (max `limit` 50000).
- `get_pinpoint(citation, paragraph=N)` **or** `get_pinpoint(citation, quote="…")` → a paragraph's text from its number, or the ¶ a quote lives in (with verbatim status). Paragraph pinpoints need ¶ markers (generally 1997+ opinions).
- `verify_citation(query, expected_case_name="…")` → `found`, canonical case name, filing date, authoring justice, the full Redbook parallel-cite set, and a ready-to-paste `formatted` cite; catches wrong volume/page/year. With `expected_case_name`, flags name drift.
- `verify_quotation(citation, quote)` → whether the quote is verbatim (whitespace/curly-quote/dash-tolerant), a word-level diff of any discrepancy, the closest actual text, and the pinpoint ¶.
- `case_summary(citation)` → one-call front matter (caption, parallel cites, date, author, panel, voting record, disposition, ¶ count). **`disposition` and `syllabus_points` are derived/heuristic — verify against the opinion.**

**Cardinal caution:** ndcourts-mcp is a research aid, not an authoritative reporter; derived fields (disposition, syllabus) and the `antecedent_name` heuristic are best-effort. Use MCP results to locate and check authority, but cite to the opinion text itself.

---

## Phase 2: Parallel Analysis (Subagents)

Launch all applicable agents **simultaneously** using the Task tool (`subagent_type: general-purpose`). Each agent gets:

- Paths to relevant `.txt` files (or PDF paths if `needs_visual_read`)
- Focused extraction instructions
- Expected output format (structured markdown)

**For Agent D** (and any agent doing citation lookups), also **copy the "Legal-Research MCP Servers" section above into the agent's prompt** — the subagent does not read this SKILL, so it needs the source precedence and tool signatures inline to prefer the MCP over the web.

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
> - Case number (format: YYYYNNNN, e.g., 20990001)
> - Case name (Party v. Party)
> - District court case number(s) (e.g., 00-0000-CV-00000) — look on the brief cover page, notice of appeal, or district court order caption. If multiple district court cases are consolidated in one appeal, list all of them with a note about which record items belong to each.
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

### Agent C2: District Court Orders (Mandatory)

**Always launch** whenever the appeal is from a district court order or judgment — which is nearly every appeal. Per the Essential-Documents Rule, the order(s) and judgment(s) on review **must** be read in full; this agent is the vehicle. The only case in which it does not run is one with no order or judgment at all (rare — confirm with the user before skipping). "The order wasn't in the manifest" is **not** a reason to skip — Step 0 requires locating it first, including by visual read of a scanned batch.

**Reads:** district court order(s) and judgment(s) text — pass the specific split record items (e.g., R7, R36, R37) isolated in Step 0, not the full record PDF. If an item is `needs_visual_read`, pass the PDF path with instructions to read those pages directly with the Read tool. After reading, the order's/judgment's `read_status` in the manifest becomes `read`.

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
> - **Every separate ground of decision, enumerated**, each with a pinpoint cite (R##:page or :¶) to where the order states it. Courts frequently rule on multiple alternative grounds (e.g., failure of proof, untimeliness, res judicata, misuse of process) — capture **all** of them, and note which the court treats as the **primary/dispositive** ground versus **alternative** grounds.
> - Any finding the court made that resolves a disputed point (distinguish a *court finding* from a party's *argument* — attribute it to the court, not to a party)
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

**Launch only if** `citations.json` contains entries with `cite_type` in `neutral_cite`, `us_supreme_court`, `federal_reporter`, or `regional_reporter`.

**Reads:** local opinion markdown files (preferred), web sources via jetcite-provided URLs (fallback)

**Input:** Pass Agent D the filtered list of case citation entries from `citations.json` — all entries where `cite_type` is `neutral_cite`, `us_supreme_court`, `federal_reporter`, or `regional_reporter`. Each entry includes `cite_type`, `jurisdiction`, `local_path`, `local_exists`, `url`, and `search_hint`.

**Prompt template:**

> **Precedent Verification**
>
> You have a list of case citations extracted from appellate briefs, with pre-resolved local paths and URLs from the citation checker. For each citation, look up the opinion and extract relevant information.
>
> **Citation data format:** Each citation entry includes:
> - `cite_text` / `normalized`: the citation string
> - `cite_type`: one of `neutral_cite`, `us_supreme_court`, `federal_reporter`, `regional_reporter`
> - `jurisdiction`: jurisdiction code (e.g., `nd`, `us`, `oh`, `wy`)
> - `local_path` / `local_exists`: path in `~/refs/` and whether the file exists
> - `url`: source URL (ndcourts.gov, CourtListener, Justia, etc.)
> - `search_hint`: text to match within the file
> - `antecedent_name`: best-effort case name preceding the cite (e.g. "State v. Smith"). Heuristic — may be `null`; use it to identify the case and to sanity-check the lookup.
> - `redundant_parallel` / `primary_cite`: if `redundant_parallel` is `true`, this entry is a parallel citation form of `primary_cite` (the same case). Verify the `primary_cite` entry once; do not separately verify the redundant one.
> - `cite_type: "pin_cite"` entries are short-form back-references (`491 F.3d at 363`, `Id. ¶ 15`) to the full cite named in `parent_normalized`. Do not look them up independently — open the parent's opinion (`parent_local_path` when `parent_local_exists`, else the parent entry's `url`) and confirm the cited `pin_page`/`pin_paragraph` exists and supports the proposition. An entry with `pin_warning` is an unresolved short form — report it as a probable citation error in the brief (check whether a digit-transposed volume or a different case was intended).
>
> ---
>
> **Sources and precedence — MCP before web.** Follow the **Legal-Research MCP Servers** precedence (included in your instructions above): prefer ndcourts-mcp for ND cites and the CourtListener MCP for other case law, falling through to local files and then the web only on a miss. For each ND case citation, verify and retrieve via ndcourts-mcp first — `verify_citation(query, expected_case_name="…")` for existence, caption, and the Redbook parallel-cite set; `verify_quotation(citation, quote)` for any quoted passage; `get_pinpoint(citation, paragraph=N)` for a pinpoint ¶; and `lookup_opinion` / `get_opinion_text` to read the opinion. For U.S. Supreme Court, federal, and other-state cites, try the CourtListener MCP. A local `~/refs/` opinion file is equally authoritative and instant — use the MCP or a local file before any web fetch. **Never go to the web for an ND case citation without first trying ndcourts-mcp or a local file.**
>
> The `local_path` and `url` fields in the citation data come from the citation checker (jetcite), which only **generates** paths and URLs — it never fetches over the network and has no knowledge of MCP. Those fields support the local and web-fallback tiers below; they do **not** mean the web should be tried before an MCP. Only fall through to the web steps if no MCP is connected and no local file exists.
>
> **Lookup strategy by citation type (web fallbacks, used only when no MCP/local source applies):**
>
> **Neutral citations (`neutral_cite`):** Any state's medium-neutral citation (e.g., 2024 ND 156, 2022-Ohio-4635).
>
> 1. **Local files (fastest, most complete):** If `local_exists` is `true`, use the Read tool on `local_path`. Paragraphs are marked `[¶N]`.
> 2. **Official court website (primary web fallback):** If `local_exists` is `false` and no MCP returned the opinion, use WebFetch on the `url` from the citation data. For ND cases, if the direct URL fails, fall back to the search endpoint:
>    ```
>    https://www.ndcourts.gov/supreme-court/opinions?cit1=YYYY&citType=ND&cit2=NNN&pageSize=10&sortOrder=1
>    ```
> 3. **CourtListener search API (secondary web fallback):** Use WebFetch:
>    ```
>    https://www.courtlistener.com/api/rest/v4/search/?q=%22{search_hint}%22&type=o
>    ```
>    Returns JSON (no auth required) with `caseName`, `neutralCite`, `syllabus`.
>
> **U.S. Supreme Court (`us_supreme_court`):**
>
> 1. **Local files:** If `local_exists` is `true`, read from `local_path`.
> 2. **Justia / CourtListener:** Use WebFetch on the `url` field.
>
> **Federal reporters (`federal_reporter`) and regional reporters (`regional_reporter`):**
>
> 1. **Local files:** If `local_exists` is `true`, read from `local_path`.
> 2. **CourtListener:** Use WebFetch on the `url` field.
> 3. **CourtListener search API (if redirect URL fails):** Use WebFetch:
>    ```
>    https://www.courtlistener.com/api/rest/v4/search/?q=%22{search_hint}%22&type=o
>    ```
>
> ---
>
> **Limitations of web fallbacks:** Web sources typically provide summary text (syllabus, headnotes), not full opinions. Pinpoint paragraph verification is not possible from web summaries.
>
> **Citations to verify:**
> [Insert citation entries from citations.json, plus the proposition each is cited for in the briefs. When `antecedent_name` is present, present each as "*antecedent_name*, <cite>" (e.g. "*State v. Smith*, 2024 ND 156") so the named case travels with its citation. Collapse parallel forms: list only the `primary_cite` of each pair and note its parallel cite alongside; omit entries marked `redundant_parallel: true` as separate items.]
>
> **Prioritization:** Focus on opinions cited for standards of review and contested holdings first. If the list exceeds 15 citations, skip string cites (citations grouped in a series without individual discussion). Prioritize ND cases (most relevant to this court's precedent), then U.S. Supreme Court cases, then federal and state cases.
>
> **For each citation:**
>
> 1. **Locate the opinion.** Prefer a connected MCP — the `ndcourts` MCP for ND cites, the CourtListener MCP for others — before the web. Otherwise use `local_path` if `local_exists`, then `url`, then CourtListener search. If none produces a result, mark as "Not found" and move on.
> 2. **Read the cited paragraph** (local: the pinpoint ¶, plus 1-2 surrounding paragraphs for context; web: use the syllabus and snippet). If no pinpoint and using local files, skim the full opinion.
> 3. **Extract the holding and key rule** from the cited paragraph(s) or syllabus.
> 4. **Assess support:** Does the cited paragraph (or syllabus) actually support the proposition it's cited for? Report: **Supports**, **Partially supports**, **Does not support**, or **Insufficient data** (when the web fallback syllabus is too sparse to assess).
> 5. **Standard of review:** If the opinion articulates a standard of review, note it.
> 6. **Name check:** If `antecedent_name` is present and the opinion you located has a clearly different case name, flag it as a possible mis-cite (wrong volume/page or wrong reporter). `antecedent_name` is heuristic — flag only clear conflicts, not formatting or abbreviation differences, and never flag when it is `null`.
>
> **Return three sections:**
>
> **A. Lookup Methods Summary:** One line tallying how the citations were located, so the reader can confirm the MCP was tried before the web. Count each citation once, by the source that actually produced the result (the `Source` column value):
>
> `Lookup methods — ndcourts MCP: N | CourtListener MCP: N | local files: N | web: N | not found: N`
>
> Then add a one-line **ND web-fallback note**: if every ND citation was resolved via the ndcourts MCP or a local file, write "All ND cites via MCP/local." If any ND citation fell through to the web, list those cites and the reason (e.g., "ndcourts MCP not connected" or "MCP returned no match"). This makes any web fallback for ND opinions explicit rather than silent.
>
> **B. Citation Verification Table:**
>
> | Citation | Type | Cited For | Source | Supports? | Holding/Key Rule | Standard of Review |
> | -------- | ---- | --------- | ------ | --------- | ---------------- | ------------------ |
>
> Source column values: "ndcourts MCP", "CourtListener MCP", "Local file", "ndcourts.gov (highlight)", "CourtListener", "CourtListener (syllabus)", "Justia", or "Not found". Record the source that actually produced the result, so the Source column and the section-A tally agree. If step 6 flags a possible mis-cite, prefix the Holding/Key Rule cell with "POSSIBLE MIS-CITE:" and state the name conflict.
>
> **C. Legal Framework Narrative:**
> For each issue area, write a brief narrative (2-4 sentences) summarizing the legal framework established by the cited cases. Group by issue.

### Agent E: Statutory, Administrative Code & Court Rule Verification (Conditional)

**Launch only if** `citations.json` contains entries with `cite_type` in `statute`, `statute_chapter`, `regulation`, `court_rule`, or `constitution`.

**Reads:** local markdown files from `~/refs/statute/`, `~/refs/reg/`, `~/refs/rule/`, and `~/refs/cnst/`

**Input:** Pass Agent E the filtered list of statutory/regulatory/rule/constitution entries from `citations.json`. Each entry includes `cite_type`, `jurisdiction`, `local_path`, `local_exists`, `url`, and `search_hint`.

**Prompt template:**

> **Statutory, Regulatory, Constitutional & Court Rule Verification**
>
> You have a list of statute, regulation, constitution, and/or court rule citations extracted from appellate briefs, with pre-resolved local paths and URLs from the citation checker. For each citation, look up the text and verify that it exists and supports the proposition it is cited for. Also verify the accuracy of any direct quotes from these sources.
>
> **Citation data format:** Each citation entry includes:
> - `cite_text` / `normalized`: the citation string
> - `cite_type`: `statute`, `statute_chapter`, `regulation`, `court_rule`, or `constitution`
> - `jurisdiction`: jurisdiction code (e.g., `nd`, `us`)
> - `local_path` / `local_exists`: path in `~/refs/` and whether the file exists
> - `url`: official source URL (ndlegis.gov, ndcourts.gov, govinfo.gov, etc.)
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

### Step 2.5: Essential-Documents Read Gate (blocking)

**GATE: Do not begin legal framing or memo generation until every essential document has been read.** This closes the Essential-Documents Rule with a hard check.

1. **Assemble the essential set:** the union of
   - every order and judgment on appeal (manifest `essential: true`), and
   - every document on Agent A's **Key Documents for Quick Reference** list, plus any document an agent flagged as highly relevant to an issue.
   
   Mark each of these `essential: true` in the manifest if not already.

2. **Confirm each was actually read.** A document counts as read only if its text (or a visual read of its pages) is present in an agent's returned analysis — not merely named, and not characterized from a brief's description of it.

3. **Read the unread.** For any essential document with `read_status: unread`, launch a targeted read now (Agent C2-style for orders; a focused subagent reading the specific record item for others, using the Step 0 retrieval procedure for scanned/buried items) and **block** until it returns. Then set `read_status: read`.

4. **Handle genuine absence:**
   - If an **order or judgment** cannot be located in the provided materials, **stop and ask the user** for it — do not proceed on inference.
   - If a **key/highly-relevant document** is genuinely not in what was provided, note this explicitly (it will be flagged in the memo and to the user) and proceed; never substitute a brief's characterization for the missing document.

Only when the essential set is fully read (or its absence explicitly flagged) may you continue to Step 3.

### Step 3: Legal Framing

For each consolidated issue:

0. **Ground the issue in the order's actual ruling.** State the district court's actual grounds of decision for this issue from Agent C2's reading of the order — enumerated, with pinpoint cites to the order (R##:page or :¶), distinguishing the primary/dispositive ground from alternative grounds. Do not characterize the ruling from the briefs. If the court decided on a threshold or dispositive ground, say so; the analysis and any strength assessment should track how the court actually disposed of the issue rather than treating every sub-question as co-equal.
1. **Determine correct standard of review** — adjudicate between the parties' positions using Agent D's precedent analysis (if available). If both sides cite the same standard, adopt it. If they disagree, assess which is correct based on the cited authorities.
2. **Identify the strongest argument supporting the district court's ruling** — articulate the best case for affirmance with specific citations.
3. **Identify the strongest counterargument** — the best case for the opposing position, with specific citations.
4. **Assess preservation** — if there's a waiver/preservation dispute, analyze it before reaching the merits.
5. **Flag statutory interpretation issues** — if the issue turns on statutory text, identify the interpretive question, the competing readings, and any relevant canons.
6. **If `strength_mode` is enabled (default)**, assess which side has the stronger argument on this issue and whether it is more consistent with the text, precedent, and established interpretive principles, with reasoning. State the assessment with appropriate qualifications and hedging and an explicit confidence level (high / moderate / low), and note what would change it. Do **not** state or imply a recommended disposition — do not say the ruling should be affirmed, reversed, or remanded, or that the Court should rule a particular way; the assessment addresses argument strength and doctrinal fit, not how the case should be decided. Where the stronger argument may still not carry the outcome (e.g., a preservation problem, the standard of review, or a dispositive threshold ground), say so and lower the confidence accordingly. For close questions, suggest one or two questions for oral argument that would press counsel on the central strength or weakness of a position. If `strength_mode` is disabled, end the analysis after presenting both sides' strongest positions without assessing which is stronger.

### Step 3.5: Interpretive Panel (Optional)

**Prerequisite:** The jetpanel skill must be installed at `~/.claude/skills/jetpanel/SKILL.md`. If it is not installed, skip this step silently.

**Activation:** Run this step when ALL of the following are true:
1. `strength_mode` is enabled (default)
2. Step 3 identified a close interpretive question — one where the legal framing shows strong arguments on both sides of a statutory or constitutional interpretation issue, competing canons, or genuine textual ambiguity

**How to invoke:** Spawn a subagent using the Agent tool with the following instructions:

> Read the jetpanel skill at `~/.claude/skills/jetpanel/SKILL.md` and execute it in integration mode.
>
> **Question Presented:** {the close interpretive question from Step 3}
>
> **Provision at Issue:** {the statute, constitutional clause, or rule}
>
> **Competing Positions:**
> - Position A: {appellant's reading with interpretive basis}
> - Position B: {appellee's reading with interpretive basis}
>
> **Relevant Authority:**
> {Key precedent from Agent D results, statutory text from Agent E results, with file paths and URLs}
>
> **Output mode:** integration — return the condensed "Interpretive Panel" section for insertion into a bench memo.

The subagent returns a condensed panel section. Insert it into the memo after the relevant issue's Analysis paragraph (Step 4), before the next issue heading or CONCLUSION. Use the `### Interpretive Panel: {Issue heading}` format.

**Multiple close questions:** If Step 3 flags more than one close interpretive question, spawn one panel subagent per question. Run them in parallel.

**Token budget note:** Each panel invocation adds ~85-170K tokens via the subagent. This runs in a separate context and does not consume the main memo's context window, but the condensed output (~200-500 tokens per question) is inserted into the main context for memo generation.

### Step 3.6: Supplemental Authority (Agent F — synthesis subagent)

The citation rule permits — and often expects — the memo to cite controlling authority the parties missed (see Important Rules). This step is how that authority enters the draft: a grounded, bounded lookup in the ND corpus, run **before** drafting so the first draft is already complete. It is a synthesis-phase subagent (distinct from the Phase 2 extraction agents), launched after Step 3 framing because it needs the issues, the provisions that are points of decision, and the cases each side leans on.

**The bounded triple — the ONLY three things Agent F looks for:**

1. **Controlling ND precedent the parties missed** on the dispositive question of an issue.
2. **Negative treatment** (overruled, superseded, abrogated, limited, called into doubt) of a case **a party leans on**.
3. **On-point ND construction of the statute or rule at issue** that the parties did not cite.

This is **not** a roving search for analogous cases, persuasive authority, or a literature review. If a candidate does not fall in the triple, it does not belong.

**Four bounding rules (all apply):**

- **Triggered, not blanket.** Run Agent F **only if** the ndcourts MCP is connected **and** Step 3 identified at least one of: a statute/rule that is a point of decision (→ triple #3), or a load-bearing case a party relies on (→ triple #1, #2). If neither, skip this step.
- **Cap + clerk standard.** At most ~2–3 supplemental authorities per issue. The test is "would a careful clerk flag this to the justice?" — controlling, material, on the dispositive question. Reject merely analogous, cumulative, or tangential hits.
- **MCP-grounded or it doesn't happen.** Every candidate must be **retrieved from the ndcourts MCP and actually read** (`search → read → cite`), never recalled from memory and then "verified." This step is **MCP-only**: no `~/refs` and no web fallback — `~/refs` is indexed by citation, not by topic, so it cannot do discovery, and open web search reintroduces the fabrication risk. If the ndcourts MCP is absent, skip the step entirely and note the limitation.
- **Neutral presentation.** Supplemental authority is reported for what it holds. If it cuts against a party (including the party who would otherwise win), say so even-handedly; added authority is not advocacy.

**How to invoke:** Launch one subagent (Task tool, `subagent_type: general-purpose`). **Copy the ndcourts-mcp tool signatures from the "Legal-Research MCP Servers" section into the prompt** (the subagent does not read this SKILL and needs the tool list) — but make clear this lookup is **MCP-only**: do not import the section's local-file/web fallback precedence here. Supply, per issue: the dispositive legal question, the provision(s) that are points of decision, the load-bearing cases each side relies on, and the brief-derived citation list (so the subagent can exclude what the parties already cited).

**Prompt template:**

> **Supplemental Authority Lookup (bounded)**
>
> For each issue below, find ND authority the parties did **not** cite, limited strictly to these three categories. Use the ndcourts MCP **only** — search the corpus and read the opinion; never propose a cite from memory, and do not fall back to local files or web search. If the ndcourts MCP is unavailable, return "MCP unavailable — no supplemental lookup performed" and stop.
>
> 1. **Controlling ND precedent the parties missed** on the dispositive question. Anchor the search to authority already in the case: `get_citing_opinions(<lead case the party cites>)` and/or `more_like_this(<lead case>)`, filtered to ND opinions that state or refine the controlling rule. Do not free-search topics.
> 2. **Negative treatment of a relied-on case:** for each load-bearing case a party cites, `check_treatment(<cite>)` and `get_subsequent_history(<cite>)`. Report only adverse treatment (overruled/superseded/abrogated/limited/doubted).
> 3. **On-point ND construction of the statute/rule at issue:** `find_opinions_construing(<provision>)`; report ND opinions construing the same provision on the point in dispute.
>
> **Exclude** anything already in this brief-derived citation list: [insert citations.json cites]. **Cap** at ~2–3 authorities per issue; include only what a careful clerk would flag to the justice — controlling and material, not merely analogous.
>
> **For each authority returned, give:** the issue it bears on; the citation; which triple category (1/2/3); the proposition it supports or the treatment it carries; a **pinpoint** (¶) you read (`get_pinpoint` / `verify_quotation`) confirming it; one line on **why it is material**; and confirmation it is **not** in the parties' briefs. If a category yields nothing material for an issue, say "none."
>
> Return a structured list grouped by issue. Do not draft memo prose.

**Use of the results in Step 4:** Incorporate each returned authority into the relevant issue's analysis, **tagged as the memo's addition** (in text or a parenthetical, e.g., "(not cited by the parties)"). These citations then flow through Step 7 (linking) and **trigger the mandatory Step 9 verification** (added authority must be verified with extra care). If Agent F returns nothing, the draft proceeds on the parties' authority alone — that is a normal outcome, not a failure.

**Degradation:** No ndcourts MCP → skip this step and note in the memo that supplemental-authority lookup was not run (corpus unavailable). Do not substitute open web search for the bounded corpus lookup.

### Step 4: Generate the Memo

**Record citation hyperlinking:** All record citations in the markdown output must be hyperlinks to `record.ndcourts.gov`. Use the district court case number from metadata to construct URLs:

- `R45` → `[R45](https://record.ndcourts.gov/Case/{dc_docket}/45)`
- `R45:12` → `[R45:12](https://record.ndcourts.gov/Case/{dc_docket}/45#page=12)`
- `R45:12:¶15` → `[R45:12:¶15](https://record.ndcourts.gov/Case/{dc_docket}/45#page=12)`

When multiple record items appear together, hyperlink each separately:
`([R240](https://record.ndcourts.gov/Case/{dc_docket}/240); [R268](https://record.ndcourts.gov/Case/{dc_docket}/268))`

**Multiple district court cases (Rule 30(b)(1)):** When the appeal consolidates multiple district court cases, each record citation must identify which case the record item belongs to, using the mapping from Agent A's metadata. The URL must use that item's district court case number. On first reference, use the full district court case number; on subsequent references, use only the last four digits:
- First: `[00-0000-CV-00000 R55:22](https://record.ndcourts.gov/Case/00-0000-CV-00000/55#page=22)`
- Later: `[0000 R55:22](https://record.ndcourts.gov/Case/00-0000-CV-00000/55#page=22)`

**Paragraph symbol rule:** Never use "para." or "paras." anywhere in the memo — always use ¶ (singular) or ¶¶ (plural). In record citations, no space between ¶/¶¶ and the number (per N.D.R.App.P. 30): `¶3`, `¶¶7–14`. In case law citations, include a space (per Bluebook): `¶ 12`, `¶¶ 6–8`.

**Length target (soft):** Aim for a **6–10 page** memo (see `memo-format.md` for the page/word proxy). To reach it, **prune facts not necessary to understand and resolve the issues on appeal** — completeness of *reading* (the Essential-Documents Rule) does not mean completeness of *recounting*. Use judgment on analytical depth: simple cases stay short; genuinely complex or multi-issue cases warrant more. **A memo over 15 pages must be justified** by multiple issues or particularly complicated issues — if it runs long for any other reason, it is over-written; cut. Reading everything essential and then writing tight are the same discipline, not opposites.

**Proof of reading:** State the district court's procedural posture and **each ground of decision** from the order itself, with a pinpoint cite to the order (e.g., `R38:2–9`). If you cannot pinpoint-cite the order's grounds, you have not read it — return to Step 2.5. Attribute court findings to the court, not to a party.

Write the complete bench memo in markdown per `memo-format.md`:

1. **Header** — case number, case name, oral argument date (omit if unknown), "Claude First Draft"
2. **Quick Reference** — 4-8 key documents with record citations (from Agent A) — every one of which was read per Step 2.5
3. **Opening [¶1]** — summarize the case and identify all issues. If `strength_mode` (default), summarize each issue's strength assessment with its confidence level (state no recommended disposition). Otherwise, state the key tension or question the case presents.
4. **BACKGROUND** — factual and procedural history with record citations for every assertion. Include the district court's grounds of decision with pinpoint cites to the order; prune facts not needed to resolve the issues.
5. **Issue sections** — Roman numerals (I., II., III.), each with:
   - Standard of review with case authority
   - Appellant's arguments with citations
   - Appellee's arguments with citations
   - Sub-arguments (A, B, C) as needed
   - Analysis and assessment — tracking the court's actual grounds; where a threshold ground is dispositive, you may note that alternative grounds need not be reached rather than developing each at equal length
   - Any **supplemental authority from Step 3.6 (Agent F)** bearing on the issue, woven into the analysis and **tagged as the memo's addition** ("(not cited by the parties)")
6. **CONCLUSION** — If `strength_mode` (default), restate each issue's strength assessment with its confidence level and the qualifications that bear on it, followed by any suggested questions for oral argument on close issues. Otherwise, summarize the key analytical considerations for each issue without assessing which side is stronger.

### Step 5: Self-Review

Review the memo against this checklist before presenting:

- [ ] **Every order and judgment on appeal was read in full** and is pinpoint-cited; its grounds of decision are stated from the order itself, not the briefs (Essential-Documents Rule / Step 2.5)
- [ ] **Every Quick Reference / key / highly-relevant document was actually read** — none is characterized solely from a party's brief; any genuinely-absent one is explicitly flagged
- [ ] **No hedging about the district court's reasoning** ("appears to," "seems," "evidently") — any such phrase is resolved by reading the order, or flagged as a true record gap
- [ ] **Length is appropriate:** ~6–10 pages typical; facts not needed to resolve the issues are pruned; if over 15 pages, the length is justified by multiple or particularly complex issues
- [ ] All issues from Step 2 are addressed
- [ ] Paragraph numbering [¶1], [¶2], etc. is sequential throughout
- [ ] Every fact in BACKGROUND has a record citation
- [ ] Each issue section has a standard of review with case authority
- [ ] **Any supplemental authority added beyond the briefs (Step 3.6) is tagged as the memo's addition, presented neutrally, and verified via the mandatory Step 9** — or none was added
- [ ] Both sides' arguments are fairly presented with citations
- [ ] Disputed facts are noted inline in BACKGROUND with both versions and cites
- [ ] Preservation is addressed for each issue (or noted as not at issue)
- [ ] Each issue analysis identifies the strongest argument for and against the district court
- [ ] Exhibit table included if ≥ 2 contested exhibits
- [ ] Writ terminology used correctly if writ proceeding
- [ ] **No recommended disposition in any mode** — the memo never states or implies that the ruling should be affirmed, reversed, or remanded, or that the Court should rule a particular way.
- [ ] If `strength_mode` (default): each issue's strength assessment appears in ¶1 and CONCLUSION, stated with an explicit confidence level (high / moderate / low) and the qualifications that bear on it.
- [ ] If `strength_mode` with close questions: suggested oral argument questions appear in CONCLUSION
- [ ] If neutral mode (`strength_mode` disabled): memo does NOT assess which side is stronger; analysis ends with both sides' positions
- [ ] No placeholder brackets like [Date], [page], [County]
- [ ] Every citation is verified (exists and supports the proposition); any authority not cited by the parties is verified with extra care and flagged as the memo's addition
- [ ] Citation formats are correct (see style-spec.md)
- [ ] Record citations include pinpoint pages where available
- [ ] If Agent D ran: its Lookup Methods Summary is reported to the user (and carried into the Step 9 appendix when verification runs), with any ND web fallback explained

Fix any issues found before presenting the memo to the user.

### Step 6: Write Output

Write the memo to a file in the current working directory:

- Default filename: `{case_number}_memo.md` (e.g., `20990001_memo.md`)
- If the user specifies a different output path, use that

When presenting the finished memo to the user, include Agent D's **Lookup Methods Summary** line (and its ND web-fallback note) in your reply, so the user can see whether ND opinions were verified against the ndcourts MCP or pulled from the web — even when Step 9 verification is not run (the brief-only case, where it remains optional). If Agent D did not run (no case citations), omit it.

### Step 6.5: jetredline Audit (Default On)

Audit the finished markdown memo with the jetredline skill, then feed its findings back into the draft. This catches prose, consistency, jurisdictional, fact, and argument-coverage issues before the memo is finalized.

**Activation:** Run by default. **Opt out** only if the user's request contains "skip audit," "no audit," or "without audit" — then skip to Step 7.

**Prerequisite:** jetredline must be installed at `~/.claude/skills/jetredline/SKILL.md`. If it is not, skip this step (and Step 6.6) silently and proceed to Step 7.

**Why a separate skill:** jetredline owns the style, consistency, and analytical-rigor rules; invoking it (rather than reimplementing them) means jetmemo inherits its future improvements. **Citation verification is deliberately excluded** — jetmemo's Step 9 is the citation authority, so the audit skips jetredline's Pass 3A/3B to avoid duplicate work.

**Invoke** one subagent (Task tool, `subagent_type: general-purpose`):

> Read the jetredline skill at `~/.claude/skills/jetredline/SKILL.md` and execute it in **audit mode** on this bench memo.
>
> - Draft (markdown): `{case_number}_memo.md`
> - Document type: memo. Output: analysis-only; **write no files**; return results to me inline.
> - Briefs/record (for Pass 4 fact-check and Pass 6 brief-matching): `[brief/record .pdf paths]`. **Text extractions already exist** as `[corresponding .txt paths]` — use them; do **not** re-run pdftotext.
> - Run passes **1, 2, 3C, 4, 5, 6**. **Skip Pass 3A/3B** (citation verification is handled separately). **Skip readability metrics** in Pass 5.
> - Preserve all markdown link syntax; never edit a URL.
> - Return exactly two parts per jetredline's audit-mode contract: (1) a ```json `edits[]` block of style `replace` edits, then (2) a "Substantive Concerns" markdown section (Jurisdiction, Fact-Check, Brief Coverage, Analytical Rigor, Negative Treatment, Style Notes).

Wait for the subagent (`TaskOutput` with `block: true`). If it fails or times out, note that the audit did not complete and proceed to Step 7 with the un-audited memo — **never block delivery on the audit.**

**Process the results:**

1. **Auto-apply mechanical edits.** For each entry in Part 1 where `type == "replace"` **and** `source_pass == "style"`, apply the change to the markdown by exact `old` → `new` replacement.
   - If `old` is not found, or matches more than one location, **do not apply** — add it to a "Could not auto-apply (review manually)" list.
   - Apply only Part 1 style edits this way. Never auto-apply anything from Part 2.
2. **Surface substantive concerns.** Hold Part 2 for the audit summary below — these are for the user's judgment, not auto-applied. The **Brief Coverage** table feeds Step 6.6.

### Step 6.6: Brief-Gap Remediation

Process the **Brief Coverage** table from the audit (Pass 6) to fill genuinely-omitted arguments before finalizing. This is the audit's highest-value feedback: an argument jetmemo never addressed will not surface in its own Step 5 self-review, because jetmemo builds its issue list from the appellant's framing.

1. **Select gaps.** Take every row marked `Addressed = No` or `Partial`. Then **filter out** rows that are correct omissions — do **not** draft fill-ins for an argument that:
   - was **waived or not preserved** (per the Step 3 preservation analysis / Agent B's waiver arguments);
   - is **mooted** by the disposition of another issue;
   - is **already treated under a different heading** (scan the memo — the brief-matcher can flag a consolidated sub-argument as missing; that is a false positive).
   
   Classify the survivors: `No` → **add**; `Partial` → **deepen**.

2. **Draft each fill-in.** Use the appellant/appellee analysis already in context (Agents A/B) first. If the argument's substance is not fully captured there, spawn a focused subagent to read **only** the cited brief span (the page range in the `Brief Source` column, from the existing `.txt`) and return a drafted section. Draft in the memo's format and voice — standard of review, the party's argument, the opposing response, and analysis — with record and authority citations like the rest of the memo.

3. **Insert** each fill-in under the correct issue heading (or as a new sub-point A/B/C), or deepen the existing partial treatment in place.

4. **Do not re-audit** the additions (avoids regress). Their new citations are verified downstream — Step 7 links them and Step 9 verifies them.

### Step 6.7: Reconcile Paragraph Numbering

After Steps 6.5–6.6, the auto-applied edits and any fill-ins may have shifted content. Re-sequence the `[¶N]` markers so numbering is sequential and contiguous throughout the memo. Do this last, immediately before Step 7. Confirm no `[¶N]` is duplicated or skipped.

**Audit summary — present to the user** (after Step 9, with the finished memo):

```
## Memo Audit (jetredline)

- Auto-applied: N style/grammar edits
- Arguments filled in: [for each — "Added: {party}'s {argument}, br. pp. X–Y" or "Deepened: …"; or "none"]
- For your review: [grouped Substantive Concerns — Jurisdiction, Fact-Check, remaining Brief Coverage notes, Analytical Rigor, Negative Treatment]
- Could not auto-apply: [list, or "none"]
```

Each filled-in argument must be listed prominently here so it is clearly a second-pass addition open to your scrutiny, not original drafting.

### Step 7: Link Authority Citations

Hyperlink citations to authority in the memo markdown. This converts bare citation text (e.g., `2024 ND 156`) into markdown links (e.g., `[2024 ND 156](url)`), so they become clickable in the docx output.

**Build a memo-derived citation list first**, then merge with the brief-derived `citations.json` from Step 1, and run `link_citations.py` against the merged file. The memo-derived list catches forms that appear in the memo but not verbatim in the briefs (e.g., `N.D.R.Civ.P. 52` cleanly parsed, vs. a multi-line jetcite artifact from the brief).

```bash
# Generate memo-derived citation list
python3 ~/.claude/skills/jetmemo/scripts/verify_citations.py --file {memo_file} --refs-dir ~/refs --json > memo_citations.json

# Merge brief + memo citations (de-dup by cite_text, prefer entries with URLs)
python3 -c "
import json
brief = json.load(open('citations.json'))
memo = json.load(open('memo_citations.json'))
merged = {}
for e in brief + memo:
    t = e.get('cite_text','').strip()
    u = e.get('url')
    if t and u and t not in merged:
        merged[t] = e
json.dump(list(merged.values()), open('merged_citations.json','w'), indent=2)
"

# Link with the enriched set
python3 ~/.claude/skills/jetmemo/scripts/link_citations.py {memo_file} merged_citations.json
```

`link_citations.py` (version ≥ 2) automatically derives short-form aliases:
- Any linked `N.D.R.{Set}.P. {N}` registers `Rule {N}` as an alias (skipped if ambiguous across rule sets).
- Any linked `N.D.C.C. § {S}` registers `§ {S}` and `Section {S}` as aliases.

Subsection references (e.g., `Rule 9(a)(3)`, `§ 27-19.1-01(5)`) are linked at the parent rule/section — the subsection is left as plain text following the link.

Citations already inside markdown links are left untouched. If `citations.json` does not exist (e.g., citation extraction was skipped), skip this step.

### Step 8: Generate Word Document

Convert the markdown memo to a formatted .docx file matching the Court's bench memo template (QTPalatine 13pt, justified, 1.2 line spacing):

```bash
python3 ~/.claude/skills/jetmemo/scripts/memo_to_docx.py {memo_file}
```

This produces `{case_number}_memo.docx` alongside the markdown file. The docx uses the same styles as the Court's bench memos: Title, Address Block (with tab-aligned metadata), Heading 1 (centered section heads), Heading 2 (issue headings), Heading 3 (sub-arguments), and Main Body Text. Page numbers appear in the footer.

If python-docx is not installed, the script will print an error. Install with `pip install python-docx`.

> **Regenerate after later edits.** Steps 9 (verification append) and 10 (provenance footer) modify the markdown after this point. Re-run `memo_to_docx.py` as the **final** action so the `.docx` reflects them — Step 10 does this for you.

### Step 9: Citation Verification (Mandatory if the memo adds non-brief authority; otherwise optional)

**When this step is required:** If the memo cites **any** authority that does **not** appear in the parties' briefs (a case, statute, rule, or constitutional provision the memo added — see the verification rule in Important Rules), this step is **mandatory**, not optional. The relaxed citation rule permits adding missed authority only on the condition that it is verified "with extra care," and this is where that verification happens. If the memo cites only authority drawn from the briefs, run this step when the user requests verification or when you want to flag potential issues.

To decide which case you are in, diff the memo's citations against the brief-derived `citations.json` from Step 1: any cite in the memo but not in the briefs is **added authority** and triggers mandatory verification (and must be tagged as the memo's addition per the Important Rules).

Run the citation checker on the finished memo:

```bash
python3 ~/.claude/skills/jetmemo/scripts/verify_citations.py --file {memo_file} --refs-dir ~/refs
```

The human-readable output shows total citations found, how many resolve locally vs. web-only vs. unresolved, grouped by type.

For JSON output (to inspect individual citations), add `--json`.

**Verify added authority with extra care.** For each added (non-brief) citation, confirm via the ndcourts MCP, a local `~/refs` source, or another authoritative source that the authority exists **and** supports the proposition it is cited for — `verify_citation` / `verify_quotation` / `get_pinpoint` for ND cases (see the Legal-Research MCP Servers section). A bare resolve by `verify_citations.py` (which only checks that a URL/path can be formed) is **not** sufficient for added authority. If an added citation cannot be confirmed to exist and support its proposition, remove it from the memo — do not ship it flagged-but-unverified.

After verification, append a summary to the memo. Carry the **Lookup Methods Summary** from Agent D (section A) into this appendix verbatim, so the finished memo shows whether ND opinions were checked against the ndcourts MCP rather than pulled from the web:

```
## CITATION VERIFICATION

Verified: X | Unverified: Y | Skipped: Z

Lookup methods (case law) — ndcourts MCP: N | CourtListener MCP: N | local files: N | web: N | not found: N
ND web-fallback: [Agent D's note — "All ND cites via MCP/local," or the list of ND cites resolved on the web and why]

### Added Authority (not cited by the parties)
- [list each citation the memo added beyond the briefs, with its verification status and source — or "None: all authority drawn from the parties' briefs"]

### Unverified Citations
- [list any citations that could not be confirmed]
```

The script's own local/web-only/unresolved counts describe URL *resolution* and are separate from the Lookup Methods tally, which reflects where Agent D actually retrieved each opinion (MCP, local, or web). Record citations (R##) reference the appellate record and are not checked by the script.

### Step 10: Stamp Provenance Footer (final step)

Stamp a provenance footer onto the finished memo so the report carries a reproducibility record — which Claude model and which jetmemo version generated it, and on what date — for later validation and comparison as the model and the skill change over time. Run this **last**, after any Step 9 verification append, then regenerate the `.docx` so the footer appears in both files:

```bash
python3 ~/.claude/skills/jetmemo/scripts/provenance.py --file {memo_file} \
  --model "{runtime model — friendly name and exact ID, e.g. Claude Opus 4.8 (claude-opus-4-8)}"
python3 ~/.claude/skills/jetmemo/scripts/memo_to_docx.py {memo_file}
```

The footer reads, e.g.: *Report generated by Claude Opus 4.8 (claude-opus-4-8) using jetmemo v3.7.0 on 2026-06-05. AI-generated first draft for internal use; verify all citations and findings before relying.*

- **Version and date are sourced deterministically by the script** — version from this skill's `SKILL.md` frontmatter (then a `VERSION` file); date from the system clock. Do not hand-type them.
- **You supply only `--model`**, using the model identifier from your runtime context — friendly name plus exact model ID. The script never infers the model itself, because a model naming its own release is exactly the unreliable self-report a validation record must not depend on.
- The stamp is **idempotent**: re-running replaces the existing footer rather than appending a duplicate, so it is safe to run on every regeneration.

---

## Token Efficiency

These strategies make it affordable to read the **whole essential set** thoroughly — they are not a budget to be protected by skipping documents. The Essential-Documents Rule overrides every row below: orders, judgments, and key documents are read in full no matter the cost, and the "fallback" of a visual read on a scanned PDF is **mandatory** for an essential document, not optional. Efficiency buys thoroughness; it never substitutes for it.

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
- **Never** let any fallback drop an essential document (order, judgment, key document). A scanned or unsplittable essential document is read visually, not skipped; a missing one is escalated to the user (Step 2.5), not inferred from the briefs.

## Important Rules

- **Read the essential documents — never guess them.** Every order, judgment, and key/highly-relevant document is read in full before analysis, regardless of length, scan quality, or token cost (see the Essential-Documents Rule and Step 2.5). Never infer an order's grounds or reasoning from the briefs; never hedge ("appears to," "seems") around a document you could read.
- **Write tight.** Read everything essential, then recount only what the issues require. ~6–10 pages is typical; prune unnecessary facts; over 15 pages must be justified by multiple or particularly complex issues.
- **Never fabricate citations; verify every citation.** Cite a case, statute, or rule only after confirming it exists and says what it is cited for — via the ndcourts MCP, a local `~/refs` source, or another authoritative source. This is an anti-fabrication and verification rule, **not** a briefs-only rule. The memo may and often should cite relevant authority the parties did not cite: identifying on-point cases, statutes, or rules the parties missed is part of assisting the Court in applying the correct law consistent with its own precedent, regardless of what the parties briefed. When citing authority neither party cited, verify it with extra care and make clear (in text or a parenthetical) that it was not cited by the parties, so the reader knows it is the memo's addition.
- **Never use placeholder brackets** like [Date], [page], [County]. If information is unavailable, omit it or write "not specified in the record."
- **Be neutral; never recommend a disposition.** Present both sides fairly before offering analysis. The memo never states or implies a recommended disposition (no affirm/reverse/remand recommendation; never that the Court should rule a particular way) in any mode. In `strength_mode` (default), it may assess which side has the stronger argument and how well each position fits the text, precedent, and established interpretive principles — always with explicit qualifications, hedging, and confidence levels, and always leaving the disposition to the Court. In neutral mode it presents the strongest arguments for each position and leaves the assessment to the reader.
- **Record citations are mandatory** for every factual assertion in BACKGROUND.
- **Use "the Court"** when referring to the ND Supreme Court; **"the district court"** for the lower court.
- **Audit feedback is graded, not blindly applied** (Steps 6.5–6.6). Auto-apply only the audit's mechanical style edits. Substantive concerns are surfaced for the user. Any argument the audit prompts you to fill in must be drafted only when it is genuinely omitted (not waived, mooted, or already covered) and must be **flagged prominently** in the audit summary as a second-pass addition.

## Writ Proceedings

When the case is a writ proceeding (petition for supervisory writ, habeas corpus, etc.):

- Use **petitioner/respondent** instead of appellant/appellee
- Agent A reads the petition; Agent B reads the response
- The opening paragraph should identify the type of writ and the relief sought
- Add a **threshold section** before the merits issues: whether the Court should exercise its supervisory jurisdiction (for supervisory writs) or whether the petition states a prima facie case (for habeas). This is Issue I in the memo.
- The "district court ruling" framing becomes "the ruling or action the petitioner seeks to challenge"
- Standard of review may differ — writs often involve questions of jurisdiction or authority, reviewed de novo
