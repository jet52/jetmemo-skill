# JetMemo Skill

Generate bench memos for the North Dakota Supreme Court from appellate case PDFs. Analyzes briefs, notices of appeal, and orders to produce structured bench memos for oral argument preparation.

## Caution: Privacy Settings Before Use

<img width="541" height="137" alt="Screenshot 2026-03-07 at 15 31 25" src="https://github.com/user-attachments/assets/b552ef6a-0e66-41f1-91b8-21b02e49b76d" />

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (CLI) installed
- `pypdf` — PDF processing library (`pip install pypdf`)
- Reference data (see [Reference Data](#reference-data) below)

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
├── Makefile
├── install.py
├── install.sh
├── .gitignore
└── skill/
    ├── SKILL.md
    ├── references/
    │   ├── memo-format.md
    │   └── style-spec.md
    └── scripts/
        ├── check_update.py
        ├── splitmarks.py
        └── verify_citations.py
```

## Reference Data

The skill uses local reference datasets for citation verification and precedent lookup. Without these, the memo will still generate but citation verification and precedent analysis will be limited.

Download the reference archives from [ndconst.org/tools](https://ndconst.org/tools) and install to `~/refs/`:

```bash
mkdir -p ~/refs
# Required for precedent verification (Agent D)
unzip opin.zip -d ~/refs/opin

# Required for statutory verification (Agent E)
unzip ndcc.zip -d ~/refs/ndcc
unzip ndac.zip -d ~/refs/ndac

# Required for court rule verification (Agent E)
unzip rule.zip -d ~/refs/rule
```

| Archive | Contents | Install to | Purpose |
|---------|----------|------------|---------|
| [opin.zip](https://ndconst.org/_media/tools/opin.zip) | ND Supreme Court opinions (1997-present) | `~/refs/opin/` | Precedent lookup and citation verification |
| [ndcc.zip](https://ndconst.org/_media/tools/ndcc.zip) | North Dakota Century Code | `~/refs/ndcc/` | Statutory text verification |
| [ndac.zip](https://ndconst.org/_media/tools/ndac.zip) | North Dakota Administrative Code | `~/refs/ndac/` | Administrative rule verification |
| [rule.zip](https://ndconst.org/_media/tools/rule.zip) | North Dakota Court Rules | `~/refs/rule/` | Court rule verification |

If `~/refs/` subdirectories are missing, the skill falls back to web lookups (ndcourts.gov, then CourtListener). Web fallbacks provide syllabus/highlight summaries but not full opinion text, so pinpoint paragraph verification is only available with local files.

## Other Dependencies

| Dependency | Purpose | Required? |
|-----------|---------|-----------|
| pypdf | Split PDF packets by bookmark | Recommended |
| [jetcite](https://github.com/jet52/jetcite) | Citation extraction and resolution | Required |

**jetcite** powers the citation checker (`verify_citations.py`). Install as a Claude skill from the GitHub repo, or via pip: `pip install git+https://github.com/jet52/jetcite.git`.
