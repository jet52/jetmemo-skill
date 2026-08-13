# JetMemo Skill

Generate bench memos from publicly filed briefs and trial court record documents. Analyzes briefs, notices of appeal, and orders to produce structured bench memos for oral argument preparation. Under continuous development, this tool assists with the most tedious and repetitive parts of case preparation (checking whether cited sources support legal or factual assertions) to help the human decision maker make better decisions.  Unlike many clerk-prepared bench memos, memos prepared by this tool make no recommended disposition.  By default they assess which side has the stronger argument — and whether it is more consistent with the text, precedent, and established interpretive principles — stated with appropriate hedging and confidence levels, never as a recommendation on how to rule.  Ask for a neutral, both-sides-only memo to suppress the assessment.  Recommended for use by courts to cross-check their internal work or by litigants to think about how courts may be breaking down the issues in a case.  Just clone this repo and ask Claude to tailor it to your jurisdiction.

## Not an Official Court Product

JetMemo is an independent, open-source project published by an individual in a
personal capacity as legal-educational software, consistent with Rule 3.1 of the
North Dakota Code of Judicial Conduct. It is not authorized, endorsed, or
maintained by the North Dakota Supreme Court or the state court system, and is
being developed without court staff, equipment, or resources. It operates only on
publicly filed documents — do not input sealed, confidential, juvenile, or other
non-public material. Its output is machine-generated: any assessment of which
argument is stronger speaks only to argument quality and doctrinal fit, and is
neither the view of the Court or any judge nor a prediction or recommendation of
how any case should or will be decided. It is not legal advice.

## Caution: Privacy Settings Before Use (turn off use of training data)

<img width="541" height="137" alt="Screenshot 2026-03-07 at 15 31 25" src="https://github.com/user-attachments/assets/b552ef6a-0e66-41f1-91b8-21b02e49b76d" />

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (CLI) installed
- `pypdf` — PDF processing library (`pip install pypdf`)
- An MCP legal-research source (see [Legal Research Sources](#legal-research-sources) below) — not strictly required, but citation verification is much weaker without one

### Optional PDF extractors

`extract_text.py` tries multiple extractors in priority order and picks the best result. Only `pypdf` is required; the others improve extraction quality for difficult PDFs:

| Extractor | Install | Notes |
|-----------|---------|-------|
| pdftotext | `brew install poppler` | Fast, often best for native-text PDFs |
| pypdf | `pip install pypdf` | **Required.** Pure Python fallback |
| PyMuPDF | `pip install pymupdf` | Good quality, fast |
| pdfplumber | `pip install pdfplumber` | Useful for table-heavy documents |
| marker | `pip install marker-pdf` | ML-based OCR for scanned/image PDFs (slow) |

## Installation

### Claude Code (CLI)

**Option A: From .zip**

1. Download and extract `jetmemo-skill.zip`
2. Run the installer:
   ```bash
   python3 install.py
   ```

**Option B: From source**

```bash
git clone https://github.com/jet52/jetmemo-skill.git
cd jetmemo-skill
python3 install.py
```

**Option C: Manual**

Copy the `skill/` directory contents to `~/.claude/skills/jetmemo/`:

```bash
mkdir -p ~/.claude/skills/jetmemo
cp -r skill/* ~/.claude/skills/jetmemo/
```

### Claude Desktop

1. Open Settings > Features > Claude's Computer Use > Skills directory
2. Set the skills directory to a folder of your choice (e.g., `~/.claude/skills/`)
3. Copy `skill/` contents into `<skills-dir>/jetmemo/`

### Claude Projects (web)

1. Open your Claude project
2. Go to Project Knowledge
3. Upload the contents of `skill/SKILL.md` as a project knowledge file

Note: The web version cannot execute scripts or access local reference files. It will produce memos using only the documents you upload to the conversation.

## Usage

Trigger phrases:
- "Generate a bench memo"
- "Draft a bench memo for this case"
- "Prepare a memo for oral argument"
- "Analyze this appeal"

Provide case documents (briefs, notices of appeal, orders) as PDFs in the working directory or attach them to the conversation.

## File Structure

```
jetmemo-skill/
├── README.md
├── VERSION
├── LICENSE
├── Makefile
├── install.py
├── install.sh
├── .gitignore
└── skill/
    ├── SKILL.md
    ├── lib/
    │   └── jetcite/          ← bundled citation library (v2.10.3)
    │       ├── models.py     ← citation data models
    │       ├── scanner.py    ← regex-based citation extraction
    │       ├── resolver.py   ← URL resolution engine
    │       ├── cache.py      ← disk cache for resolved URLs
    │       ├── patterns/     ← citation patterns by jurisdiction
    │       └── sources/      ← URL source modules (ndcourts, courtlistener, etc.)
    ├── references/
    │   ├── memo-format.md
    │   ├── model-comparison.md
    │   ├── nd-citation-style.md
    │   └── style-spec.md
    └── scripts/
        ├── check_update.py
        ├── ensure_refs.py    ← auto-detects Cowork mounted refs
        ├── extract_text.py   ← multi-library PDF text extraction
        ├── link_citations.py
        ├── memo_to_docx.py
        ├── splitmarks.py     ← record-packet splitter (v2.2.0)
        ├── textquality.py    ← text-layer scorer behind `--check-text`
        └── verify_citations.py
```

## Legal Research Sources

Citation verification and precedent lookup run against MCP servers. Without either
one connected the memo still generates, but every citation resolves by web fetch —
slower, and limited to whatever summary a public page exposes rather than full text
with paragraph pinpoints.

### ndlaw — North Dakota primary law (strongly recommended)

Covers the whole ND corpus: **opinions 1889–present** (20,000+, current to within a
day), the **Constitution**, the **Century Code**, **court rules**, the
**Administrative Code**, and **Attorney General** and **Judicial Ethics Advisory
Committee** opinions. It also carries what a flat text file cannot express — a
citator (`check_treatment`, `get_subsequent_history`), cross-references, and
**effective-date versioning**, so a provision can be read as it stood on the date
the district court applied it rather than as it reads today.

Two ways to connect:

| | Endpoint | Notes |
|---|---|---|
| **Self-hosted** (recommended) | [`ndlaw-mcp`](https://github.com/jet52/ndlaw-mcp) over stdio | Per-call latency in single-digit milliseconds against roughly 100–250 ms for the remote, and it works with no network at all — which is what makes it usable in sandboxes that block outbound HTTP. |
| **Hosted** | `https://ndlaw.org/mcp` | Nothing to install. Add it as a remote MCP connector. |

Either way the skill finds the tools by *name*, not by namespace prefix, so it works
whether they arrive as `mcp__ndlaw__*`, `mcp__claude_ai_ndlaw__*`, or anything else
your host assigns. If you connect more than one, prefer the local server.

### CourtListener — everything outside North Dakota

Supplies the case law ndlaw does not carry: U.S. Supreme Court, federal, and
other-state opinions, plus any ND opinion missing from the ND corpus. Connect it as
a remote MCP server; no API key is required for the search endpoints the skill uses.

### Precedence

The skill applies this order at every lookup and falls through on a miss:

1. **ndlaw** — every ND authority: cases, statutes, rules, constitution, admin code.
2. **CourtListener** — non-ND cases.
3. **Web** — official sources via URLs generated by the bundled jetcite
   (ndcourts.gov, ndlegis.gov, govinfo.gov, Cornell LII, CourtListener, Justia).

It will not go to the web for any ND authority without trying ndlaw first, and Agents
D and E each report which tier produced each result — so a web fallback for ND
material is visible in the finished memo rather than silent.

**Non-ND statutes and rules** — U.S.C., C.F.R., the federal rules, the U.S.
Constitution — have no MCP tier, since CourtListener indexes case law rather than
codes. Those resolve at tier 3 by web fetch to the official source.

> **Optional local cache.** If a `~/refs/` tree exists, the skill will read from it
> and `verify_citations.py --cache` will grow it as it goes. It is no longer part of
> setup: ndlaw supersedes it for ND material and is strictly better. Its remaining
> use is offline or egress-blocked operation.

### Cowork (sandboxed environments)

Self-hosted ndlaw is the best answer here, because it needs no network at all.

If you rely on web fallbacks instead, Cowork blocks outbound access by default. Add
the domains listed in [`skill/lib/jetcite/NETWORK.md`](skill/lib/jetcite/NETWORK.md)
to the egress allowlist (sandbox settings → **Allow network egress** → **Additional
allowed domains**), then start a new session. Without this, citations resolve to a
search URL rather than the direct source. A `~/refs` folder mounted via the Cowork
folder picker is auto-detected and symlinked at startup.

## Other Dependencies

| Dependency | Purpose | Required? |
|-----------|---------|-----------|
| pypdf | PDF text extraction and packet splitting | Required |
| [jetcite](https://github.com/jet52/jetcite) v2.10.3 | Citation extraction and URL resolution | Bundled |
| [ndlaw-mcp](https://github.com/jet52/ndlaw-mcp) | ND primary law — cases, statutes, rules, constitution, admin code | Strongly recommended |
| [CourtListener MCP](https://www.courtlistener.com/) | Non-ND case law | Recommended |
| [jetpanel](https://github.com/jet52/jetpanel) | Multi-perspective interpretive analysis | Optional |
| [jetredline](https://github.com/jet52/jetredline) v4.4.0+ | Memo audit (style, consistency, fact/brief coverage) | Optional |

**jetcite** is bundled in `skill/lib/jetcite/`. To update to the latest version, clone the [jetcite repo](https://github.com/jet52/jetcite) alongside this one and run `make vendor-jetcite`.

**splitmarks** and **textquality** are bundled in `skill/scripts/`. Both come from the [splitmarks repo](https://github.com/jet52/splitmarks); clone it alongside this one and run `make vendor-splitmarks`, which vendors the pair. They must stay together — `splitmarks --check-text` imports `textquality` to tell a text layer that is *missing* from one that is *present but garbage*, and without the module beside it the check silently falls back to counting characters, which cannot see the second case. `make test` fails if either has drifted from canonical.

**jetpanel** provides multi-perspective legal analysis from competing jurisprudential methodologies. When both skills are installed, jetmemo automatically invokes jetpanel for close interpretive questions (now the default; suppressed only in neutral mode). Install it separately from the [jetpanel repo](https://github.com/jet52/jetpanel).

**jetredline** audits the finished memo (Steps 6.5–6.6). When installed, jetmemo invokes it by default in audit mode: it auto-applies mechanical style edits, surfaces substantive concerns for review, and drafts fill-ins for genuinely-omitted brief arguments. Citation verification is excluded (Step 9 owns it). Opt out with "skip audit." Requires jetredline v4.4.0+ (audit mode); install it separately from the [jetredline repo](https://github.com/jet52/jetredline).

## Contributing

On a fresh clone, activate the local pre-push sensitive-content check:

```bash
git config --local core.hooksPath .githooks
```

It scans commits being pushed for likely ND court dockets, confidential-case
captions, and committed binaries. Bypass once with `git push --no-verify`.
