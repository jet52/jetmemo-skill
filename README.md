# Bench Memo Skill

Generate bench memos for the North Dakota Supreme Court from appellate case PDFs. Analyzes briefs, notices of appeal, and orders to produce structured bench memos for oral argument preparation.

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (CLI) installed
- `splitmarks` — PDF bookmark splitter ([github.com/jet52/splitmarks](https://github.com/jet52/splitmarks))
- Local reference directories:
  - `~/refs/opin/` — ND Supreme Court opinions (markdown)
  - `~/refs/ndcc/` — North Dakota Century Code
  - `~/refs/ndac/` — North Dakota Administrative Code

## Installation

### Claude Code (CLI)

**Option A: From .zip**

1. Download and extract `bench-memo-skill.zip`
2. Run the installer:
   ```bash
   bash install.sh
   ```

**Option B: From source**

```bash
git clone https://github.com/jet52/bench-memo-skill.git
cd bench-memo-skill
make install
```

**Option C: Manual**

Copy the `skill/` directory contents to `~/.claude/skills/bench-memo/`:

```bash
mkdir -p ~/.claude/skills/bench-memo
cp -a skill/* ~/.claude/skills/bench-memo/
```

### Claude Desktop

1. Open Settings > Features > Claude's Computer Use > Skills directory
2. Set the skills directory to a folder of your choice (e.g., `~/.claude/skills/`)
3. Copy `skill/` contents into `<skills-dir>/bench-memo/`

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
bench-memo-skill/
├── README.md
├── Makefile
├── install.sh
├── .gitignore
└── skill/
    ├── SKILL.md
    ├── references/
    │   ├── memo-format.md
    │   └── style-spec.md
    └── scripts/
        └── verify_citations.py
```

## External Dependencies

| Dependency | Purpose | Required? |
|-----------|---------|-----------|
| splitmarks | Split PDF packets by bookmark | Recommended |
| ~/refs/opin/ | ND opinion lookup | Recommended |
| ~/refs/ndcc/ | Century Code lookup | Recommended |
| ~/refs/ndac/ | Admin Code lookup | Recommended |
