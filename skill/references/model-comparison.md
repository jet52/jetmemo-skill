# Subagent Model Comparison Mode (test feature — off by default)

A/B test the models behind jetmemo's subagents. Each participating agent slot is
dispatched **three times with an identical prompt and identical inputs** — once
to Opus, once to Opus again (the control), once to Sonnet — and the three
outputs are compared on quality, wall-clock time, and token cost.

This is instrumentation for the skill's own development, not a memo feature. It
roughly triples Phase 2 cost and substantially lengthens wall clock. **Never run
it unless the user explicitly asks.**

---

## 1. Activation

Run this mode **only** when the user's request contains one of:

- "subagent comparison test"
- "model comparison test"
- "compare subagents"
- "model bakeoff"
- "run comparison test"

Absent one of those phrases, ignore this file entirely and run the normal
pipeline. Do not offer, suggest, or infer the mode.

**Narrowing.** If the user names specific slots ("comparison test on C2 and D"),
run only those. Otherwise run every participating slot that the case triggers.

**Arms.** Three by default: `opus`, `opus2` (a second Opus run — the control),
`sonnet`. If the user says "no control" or "two arms," drop `opus2` — but say
in the final report that the results have no noise floor and are therefore
anecdote rather than evidence.

---

## 2. Participating slots

| Slot | Agent | Participates |
| ---- | ----- | ------------ |
| A | Appellant brief analysis | yes |
| B | Appellee brief analysis | yes |
| C1 | Reply brief | yes, when it runs |
| C2 | District court orders | yes |
| C3 | Hearing transcript | yes, when it runs |
| D | Precedent lookup | yes |
| E | Statute/rule verification | yes |
| F | Supplemental authority (Step 3.6) | yes, when it runs |
| Step 2.5 targeted reads | — | no |
| jetpanel (Step 3.5) | — | no |
| jetredline audit (Step 6.5) | — | no |
| Brief-gap fill-in (Step 6.6) | — | no |

The excluded slots either mutate the draft or are another skill's work; leave
them single-dispatch so the comparison never changes what ships.

---

## 3. Fair-test rules (non-negotiable)

1. **Byte-identical prompts.** All arms of a slot receive the same prompt text,
   the same file paths, and the same citation entries. Build the prompt once,
   then send it to each arm unchanged. Never tailor a prompt to a model.
2. **No test-awareness.** No arm is told it is in a comparison, which model it
   is, or that another arm exists. A subagent that knows it is being graded is
   not measuring what you want.
3. **Same tools, same resources.** Identical `subagent_type`; same MCP
   availability; same `~/refs`. Do not vary effort settings between arms — model
   is the only variable.
4. **Description tag.** Every dispatched `Agent` call sets
   `description: "cmp <slot> <arm>"` — e.g. `cmp A opus`, `cmp A opus2`,
   `cmp D sonnet`. The metrics script pairs runs by parsing this tag; a
   mistyped tag drops the run from the report.
5. **Model override.** Set `model: "opus"` on the `opus` and `opus2` arms and
   `model: "sonnet"` on the `sonnet` arm. The harvest script verifies against
   the `resolvedModel` the runtime actually used and flags any mismatch.

---

## 4. Scheduling: paired-parallel, slot by slot

Dispatch **all arms of one slot together in a single message**, wait for all of
them, then move to the next slot. Do not fan out every slot at once.

The pair — not the run — is the unit of comparison, so the arms of a slot must
face the same system load for the duration figure to mean anything. Slot-by-slot
also keeps concurrency at 2–3 instead of 20+.

This makes a comparison run take far longer in wall clock than a normal memo
run. That is expected; say so to the user when the mode starts.

---

## 5. The Opus arm is canonical

The memo is built from the **`opus`** arm's output for every slot, always. The
`opus2` and `sonnet` outputs are measured and reported, never shipped.

If Sonnet (or Opus₂) caught something the canonical arm missed — a record cite,
an issue, an exhibit, a mis-cite — **do not silently merge it**. List it in the
report under "Missed by the canonical arm" so the user can decide. This keeps
the delivered memo attributable to one model and keeps the comparison honest.

---

## 6. Output layout

Write everything under `./.model-comparison/{case_number}/`:

```
.model-comparison/20990001/
  A.opus.md          A.opus2.md          A.sonnet.md
  C2.opus.md         C2.opus2.md         C2.sonnet.md
  ...
  judge.A.md         judge.C2.md         ...     # blind scorecards
  metrics.md                                     # compare_agents.py output
  report.md                                      # the synthesis you present
```

Write each arm's raw returned output verbatim, before any editing. These
accumulate across cases and are the corpus for later meta-analysis, so do not
prune them.

---

## 7. Quality scoring

### 7a. Blind judge (one per slot)

After a slot's arms return, spawn **one Opus judge subagent per slot**. The
judge must not know which model wrote which output.

- Randomize presentation order per slot:
  `python3 -c "import random; print(random.choice(['AB','BA']))"`.
- Label the outputs **Output 1** and **Output 2** only. Strip filenames,
  model names, and any arm wording.
- Judge the `opus` vs `sonnet` pair. Judge `opus` vs `opus2` as a second,
  separately-labelled pair when the control arm ran — the judge should not be
  told that either pair is same-model.

**Judge prompt skeleton:**

> You are grading two independent analyses of the same source documents,
> produced from an identical prompt. You do not know who wrote either.
>
> Source documents: `[paths]`
> The prompt both analysts received: `[verbatim prompt]`
>
> Output 1: `[verbatim]`
> Output 2: `[verbatim]`
>
> Score each output 1–5 on each criterion below, with a one-sentence
> justification per score citing specific text. Then:
>
> 1. List every **factual disagreement** between the two — a record cite, a
>    date, a holding, a verdict, a name where they differ — with the location
>    in each output. Do not resolve them; just enumerate.
> 2. List anything one output contains that the other omits entirely.
> 3. State which output you would rather hand a justice, and why, in two
>    sentences. Say "no meaningful difference" if that is the honest answer.
>
> Length is not quality. A longer output that repeats the briefs is worse than
> a shorter one that pinpoints them. Do not reward volume.

### 7b. Per-slot rubrics

Give the judge the rubric for the slot being scored.

**Extraction slots (A, B, C1, C3)**
- **Completeness** — every numbered section of the prompt is present and
  populated; no section answered with a placeholder.
- **Citation precision** — record cite with pinpoint page and a short
  identifying quote for each factual assertion, as the prompt requires.
- **Fidelity** — nothing asserted that the source does not say; party
  arguments attributed to the party, not stated as fact.
- **Issue structure** (A) — sub-arguments under one legal theory consolidated
  as A/B/C; distinct theories kept separate.
- **Discipline** — extraction only; no analysis or recommendation smuggled in.

**C2 — district court orders**
- **Grounds enumeration** — *every* separate ground of decision captured, each
  pinpoint-cited, with primary/dispositive distinguished from alternative.
- **Attribution** — court findings attributed to the court, not to a party.
- **No hedging** — states what the order says; no "appears to," "seems."

**D — precedent lookup**
- **Verification correctness** — the Supports / Partially / Does not support
  verdict matches what the cited paragraph actually holds.
- **Source discipline** — MCP or local file tried before the web for ND cites;
  the Lookup Methods tally matches the Source column.
- **Repair handling** — splice-suspect and pin-cite entries handled per the
  prompt; no cite declared nonexistent without attempting the repair.
- **Honesty** — "Not found" where not found; no fabricated holdings.

**E — statutes, rules, regulations**
- **Location accuracy** — correct section/subsection retrieved.
- **Quote verification** — brief's quotation actually compared to the text, and
  the discrepancy call is right.
- **Support assessment** — verdict matches the provision's text.

**F — supplemental authority**
- **Bounded-triple discipline** — every candidate falls in one of the three
  categories; no roving topical search.
- **MCP-grounded** — each authority retrieved and read, with a pinpoint the
  agent actually confirmed; nothing recalled from memory.
- **Materiality** — clears the careful-clerk bar; not merely analogous.
- **Exclusion** — nothing returned that the parties already cited.
- **Neutrality** — reported for what it holds, including against the party who
  would otherwise win.

### 7c. Ground-truth spot-check (do this yourself)

The judge's factual-disagreement list is the highest-value output of the whole
run, because those items are *checkable*. For each disagreement, resolve it
against the source — read the brief page, the order paragraph, the opinion ¶,
the statute — and record which arm was right.

An arm that is wrong on a verifiable fact is a finding. An arm the judge merely
found more pleasant to read is not. Weight the report accordingly.

---

## 8. Metrics harvest

After all slots finish, run:

```bash
python3 ~/.claude/skills/jetmemo/scripts/compare_agents.py \
  --out .model-comparison/{case_number}/metrics.md
```

It reads the session transcript, pairs runs by the `cmp <slot> <arm>` tag, and
reports per-arm duration, total tokens, output tokens, cache reads, tool-call
counts, and estimated cost, plus arm totals and any arm/model mismatch.

If it reports no tagged runs, the `description` fields were malformed — the
outputs are still on disk, but the objective metrics for that run are lost.

---

## 9. Reporting to the user

Write `report.md` and present it. Structure:

1. **Metrics table** — from `metrics.md`, per slot and in total.
2. **Noise floor first.** State the Opus vs Opus₂ spread before stating the
   Opus vs Sonnet spread. If the two are comparable, say plainly that the run
   did not distinguish the models on that slot.
3. **Quality per slot** — the blind judge's scores, then your own read, then
   the resolved factual disagreements with which arm was right.
4. **Missed by the canonical arm** — anything a non-canonical arm caught that
   the shipped memo lacks.
5. **Failures** — any arm that errored, timed out, or resolved to the wrong
   model.

### Interpretation guardrails (state these; do not bury them)

- **N=1 per slot.** A single case is an anecdote. Real conclusions need the same
  case run repeatedly, or many cases pooled from `.model-comparison/`.
- **The control arm is the yardstick.** An Opus–Sonnet gap smaller than the
  Opus–Opus₂ gap is noise. Say so rather than reporting it as a result.
- **Token counts are comparable; cost is more robust.** Opus 5 and Sonnet 5 are
  believed to share a tokenizer family, so raw token counts compare directly —
  but the script's cost figure prices each model at its own rate and is the
  safer headline number. (Moderate confidence on the tokenizer claim; the cost
  figure does not depend on it.)
- **Timing is load-dependent.** Paired-parallel dispatch equalizes load within a
  pair, not across slots. Do not compare a slot's duration to another slot's.
- **Do not aggregate scores into a single verdict.** Report per slot. A model
  can be better at reading orders and worse at verifying citations.
