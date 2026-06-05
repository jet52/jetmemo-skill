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
- Reference data (see [Reference Data](#reference-data) below)

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
    │   └── jetcite/          ← bundled citation library (v2.1.2)
    │       ├── models.py     ← citation data models
    │       ├── scanner.py    ← regex-based citation extraction
    │       ├── resolver.py   ← URL resolution engine
    │       ├── cache.py      ← disk cache for resolved URLs
    │       ├── patterns/     ← citation patterns by jurisdiction
    │       └── sources/      ← URL source modules (ndcourts, courtlistener, etc.)
    ├── references/
    │   ├── memo-format.md
    │   └── style-spec.md
    └── scripts/
        ├── check_update.py
        ├── ensure_refs.py    ← auto-detects Cowork mounted refs
        ├── extract_text.py   ← multi-library PDF text extraction
        ├── link_citations.py
        ├── memo_to_docx.py
        ├── splitmarks.py
        └── verify_citations.py
```

## Reference Data

The skill uses local reference datasets for citation verification and precedent lookup. Without these, the memo will still generate but citation verification and precedent analysis will be limited.

Download the reference archives from the [jetcite v2.0.0 release](https://github.com/jet52/jetcite/releases/tag/v2.0.0) and install to `~/refs/`:

```bash
mkdir -p ~/refs

# Opinions — precedent verification (Agent D)
unzip nd-opin-markdown.zip -d ~/refs/opin/ND
unzip nd-opin-NW2d.zip -d ~/refs/opin/NW2d
unzip nd-opin-NW.zip -d ~/refs/opin/NW

# Statutes and regulations — statutory verification (Agent E)
unzip nd-code.zip -d ~/refs/statute/NDCC
unzip nd-regs.zip -d ~/refs/reg/NDAC

# Court rules and constitution (Agent E)
unzip nd-rule.zip -d ~/refs/rule
unzip nd-cnst.zip -d ~/refs/cnst/ND
```

| Archive | Contents | Install to | Purpose |
|---------|----------|------------|---------|
| [nd-opin-markdown.zip](https://github.com/jet52/jetcite/releases/download/v2.0.0/nd-opin-markdown.zip) | ND opinions by neutral cite (2024 ND 156) | `~/refs/opin/ND/` | Precedent lookup — paragraph-level |
| [nd-opin-NW2d.zip](https://github.com/jet52/jetcite/releases/download/v2.0.0/nd-opin-NW2d.zip) | ND opinions by N.W.2d cite | `~/refs/opin/NW2d/` | Precedent lookup — regional reporter |
| [nd-opin-NW.zip](https://github.com/jet52/jetcite/releases/download/v2.0.0/nd-opin-NW.zip) | ND opinions by N.W. cite | `~/refs/opin/NW/` | Precedent lookup — early reporter |
| [nd-code.zip](https://github.com/jet52/jetcite/releases/download/v2.0.0/nd-code.zip) | North Dakota Century Code | `~/refs/statute/NDCC/` | Statutory text verification |
| [nd-regs.zip](https://github.com/jet52/jetcite/releases/download/v2.0.0/nd-regs.zip) | North Dakota Administrative Code | `~/refs/reg/NDAC/` | Administrative rule verification |
| [nd-rule.zip](https://github.com/jet52/jetcite/releases/download/v2.0.0/nd-rule.zip) | North Dakota Court Rules | `~/refs/rule/` | Court rule verification |
| [nd-cnst.zip](https://github.com/jet52/jetcite/releases/download/v2.0.0/nd-cnst.zip) | North Dakota Constitution | `~/refs/cnst/ND/` | Constitutional text verification |

If `~/refs/` subdirectories are missing, the skill falls back to web lookups (ndcourts.gov, then CourtListener). Web fallbacks provide syllabus/highlight summaries but not full opinion text, so pinpoint paragraph verification is only available with local files.

### Cowork (sandboxed environments)

In Cowork, `~/refs` doesn't persist across sessions. To use local references, mount your `refs` directory via the Cowork folder picker. At startup the skill auto-detects a mounted folder named `refs` and symlinks `~/refs` to it — no manual setup needed.

**Network access for citation URLs.** Web fallbacks and ND opinion PDF resolution require outbound access to official-source domains (ndcourts.gov, courtlistener.com, etc.), which Cowork blocks by default. Add the domains listed in [`skill/lib/jetcite/NETWORK.md`](skill/lib/jetcite/NETWORK.md) to the Cowork egress allowlist (sandbox settings → **Allow network egress** → **Additional allowed domains**), then start a new session. Without this, ND citations resolve to a search URL rather than the direct opinion PDF.

## Other Dependencies

| Dependency | Purpose | Required? |
|-----------|---------|-----------|
| pypdf | PDF text extraction and packet splitting | Required |
| [jetcite](https://github.com/jet52/jetcite) v2.1.2 | Citation extraction and URL resolution | Bundled |
| [jetpanel](https://github.com/jet52/jetpanel) | Multi-perspective interpretive analysis | Optional |
| [jetredline](https://github.com/jet52/jetredline) v4.4.0+ | Memo audit (style, consistency, fact/brief coverage) | Optional |

**jetcite** is bundled in `skill/lib/jetcite/`. To update to the latest version, clone the [jetcite repo](https://github.com/jet52/jetcite) alongside this one and run `make vendor-jetcite`.

**jetpanel** provides multi-perspective legal analysis from competing jurisprudential methodologies. When both skills are installed, jetmemo automatically invokes jetpanel for close interpretive questions (now the default; suppressed only in neutral mode). Install it separately from the [jetpanel repo](https://github.com/jet52/jetpanel).

**jetredline** audits the finished memo (Steps 6.5–6.6). When installed, jetmemo invokes it by default in audit mode: it auto-applies mechanical style edits, surfaces substantive concerns for review, and drafts fill-ins for genuinely-omitted brief arguments. Citation verification is excluded (Step 9 owns it). Opt out with "skip audit." Requires jetredline v4.4.0+ (audit mode); install it separately from the [jetredline repo](https://github.com/jet52/jetredline).

## Contributing

On a fresh clone, activate the local pre-push sensitive-content check:

```bash
git config --local core.hooksPath .githooks
```

It scans commits being pushed for likely ND court dockets, confidential-case
captions, and committed binaries. Bypass once with `git push --no-verify`.
