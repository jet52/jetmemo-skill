# Plan: Integrate jetcite into jetmemo-skill

## Context

jetcite is a Python library that extracts, normalizes, and resolves legal citations. It replaces the ad-hoc regex extraction and manual path construction currently spread across `verify_citations.py` and the SKILL.md agent prompts.

jetredline already integrated jetcite (commits `7002d43`–`11465ba`). This plan follows the same pattern: a thin wrapper script that calls jetcite and outputs structured JSON, consumed by the SKILL.md agents.

## Architecture: wrapper script pattern (from jetredline)

jetredline's integration established the pattern:

1. **One wrapper script** (`nd_cite_check.py`) imports jetcite and outputs a JSON array of citation records
2. **jetcite does:** extraction (`scan_text`), local path resolution (`_citation_path`), URL generation (`Citation.sources`)
3. **The script does:** legacy type mapping, search hint generation, CLI interface
4. **Agents consume** the JSON output — they never call jetcite directly
5. **Agent-specific logic** (CourtListener search API, within-file section search, quote verification) stays in the agent prompts

jetmemo should do the same with `verify_citations.py`.

## Step-by-step changes

### 1. Rewrite `verify_citations.py` as a jetcite wrapper

**Current** (~270 lines): three `extract_*` functions with inline regexes, `verify_local()` with manual path construction, `verify_nd_courts()` and `verify_statute()` with HTTP calls, `verify_courtlistener()` with API call.

**New** (~150 lines): model on jetredline's `nd_cite_check.py`:

- **jetcite import with fallback:** pip install → `~/.claude/skills/jetcite-skill/src/` → error with install instructions
- **`scan_text(text, refs_dir=...)`** replaces the three `extract_*` functions and `verify_local()`
- **`_citation_path()`** from `jetcite.cache` for explicit local path lookups
- **`Citation.sources`** for URLs (replaces `verify_nd_courts()` and `verify_statute()`)
- **`_legacy_cite_type()`** mapping (reuse from jetredline or duplicate — it's small)
- **`_search_hint()`** for in-file search terms
- **Keep the CLI interface:** `--file`, `--refs-dir`, `--json` flags
- **Keep the human-readable summary output** (verified/unverified/skipped counts) — useful for Step 7
- **Drop** inline HTTP verification (`verify_nd_courts`, `verify_statute`, `verify_courtlistener`) — agents handle web fallback themselves using URLs from the JSON output

Output schema (per citation):
```json
{
  "cite_text": "2024 ND 156",
  "cite_type": "nd_case",
  "normalized": "2024 ND 156",
  "url": "https://www.ndcourts.gov/supreme-court/opinion/2024ND156",
  "search_hint": "2024ND156",
  "local_path": "/Users/jerod/refs/opin/markdown/2024/2024ND156.md",
  "local_exists": true
}
```

### 2. Update SKILL.md Phase 1, Step 1 (citation extraction)

**Current** (lines 134-138): four separate grep patterns against `.txt` files.

**New:** single script invocation:
```bash
python3 ~/.claude/skills/jetmemo/scripts/verify_citations.py --file combined.txt --refs-dir ~/refs --json
```

The JSON output tells the orchestrator which citation types are present, determining whether to launch Agents D and E:
- Any `cite_type` in `{nd_case}` → launch Agent D
- Any `cite_type` in `{ndcc, ndcc_chapter, ndac, nd_court_rule, nd_const}` → launch Agent E

This catches more citation types than the current grep patterns (including federal citations, which agents can use or ignore).

### 3. Update Agent D (Precedent Lookup) instructions

**Current:** Agent D constructs file paths manually, builds ndcourts.gov search URLs inline, and has CourtListener as a secondary fallback.

**New:** Agent D receives the JSON output from `verify_citations.py` (filtered to `cite_type == "nd_case"`). For each citation:

1. If `local_exists` is `true`: read `local_path`, locate the pinpoint paragraph, verify
2. If `local_exists` is `false`: use `url` from JSON with WebFetch (jetcite generates the direct ndcourts.gov opinion URL)
3. If that fails: CourtListener search API as last resort (agent-specific — same endpoint as today)

This mirrors jetredline's Pass 3B exactly. The agent prompt still describes the three-tier fallback, but the path construction and URL generation are done by the script.

### 4. Update Agent E (Statutory/Code/Rule Verification) instructions

**Current:** Agent E constructs file paths manually from citation components and has web fallback URLs inline.

**New:** Agent E receives the JSON output filtered to `{ndcc, ndcc_chapter, ndac, nd_court_rule, nd_const}`. For each citation:

1. If `local_exists` is `true`: read `local_path`, search for `search_hint` within the file
2. If `local_exists` is `false`: use `url` from JSON with WebFetch

The within-file search logic (finding `### §` headings, subsections, comparing quoted text) stays in the agent prompt — that's content analysis, not citation resolution.

### 5. Update Step 7 (Citation Verification)

Step 7 currently duplicates much of what Agents D and E do. Simplify to: run `verify_citations.py` on the finished memo and append the summary. The script's human-readable output already provides the verified/unverified/skipped counts.

### 6. Dependencies and installation

- Add jetcite as an optional dependency in README.md
- Same discovery pattern as jetredline: pip import → skill directory fallback → error message with GitHub link
- No changes to `install.py` or `install.sh` (jetcite installs itself as a skill or via pip)

## Files to modify

1. **`skill/scripts/verify_citations.py`** — rewrite as jetcite wrapper
2. **`skill/SKILL.md`** — Phase 1 Step 1 extraction, Agent D prompt, Agent E prompt, Step 7
3. **`README.md`** — note jetcite dependency

## What stays unchanged

- Agents A, B, C1, C2, C3 — no citation logic
- `splitmarks.py` — unrelated
- `memo-format.md` — memo template, not citations
- `style-spec.md` — citation format specs (jetcite was built for the same conventions)
- Agent-specific content analysis: reading opinion text, checking paragraph support, comparing quoted statute text, quote verification
- CourtListener search API as last-resort fallback in Agent D (different endpoint than jetcite uses)
- The `~/refs/` directory layout documentation in SKILL.md (still useful as reference, and matches jetcite's path mapping)

## Decisions resolved

1. **`fetch_and_cache()` vs. search endpoints:** Not using either. Agents do their own web fetches using URLs from the JSON output, same as jetredline. This keeps the agents in control of when and how they fetch.

2. **Federal citations:** `scan_text()` returns them naturally. The wrapper includes them in output. Agents can use or ignore them — no filtering needed at the script level.

3. **jetcite coverage gaps:** The wrapper script is the single point of extraction. If jetcite misses something the old grep patterns caught, we fix it in jetcite, not in jetmemo. Test with real brief text before shipping.
