# tailorswif — phase 0

Builds **one 50-second sequence**: twelve shots, one street, one escalating
rule. Costs **$9.86**. Ends with a video you can send someone.

This does not generate full music videos. That is deliberate. The riskiest
unknown is not the pipeline — it is whether the register is reachable at all
with current models, and whether twelve separately generated shots hold together
as one place. Find that out for $10 before building anything.

## The sequence

One rule: *objects heavier than a car have stopped being held down.* It arrives
in five stages across the cut.

| stage | shots | what you see |
|---|---|---|
| 0 | 1–3, 12 | the street behaving normally |
| 1 | 4–5 | one car sits slightly too high, easy to miss |
| 2 | 6–7 | it is unmistakable, and nobody reacts |
| 3 | 8–10 | it is everywhere |
| 4 | 11 | the rule has taken the street |

Every shot inherits the same written location, and at least one *invariant*
stays visible throughout — litter lying flat, people walking at an ordinary
pace, the light unchanged. That is what makes the strangeness read as designed
rather than random.

Staging varies across the twelve shots (roughly three per strategy), so the run
still tells you which blocking works:

| | anomaly foregrounded | anomaly in background |
|---|---|---|
| **faces visible** | `faces_primary` | `faces_suppressed` |
| **no faces** | `backs_primary` | `backs_suppressed` |

Hypothesis: `backs_suppressed` reads best and `faces_primary` looks like every
other AI video. Being wrong about that cheaply is the point.

Three shots are also rendered on Kling and Veo as **probes**, so you still get a
model comparison out of a run whose main job is producing a cut.

## Run it

```bash
uv run tailorswif plan             # shot list and cost, spends nothing
uv run tailorswif plan -v          # ... with the full prompts
uv run tailorswif run              # dry run — prompt sidecars, $0
uv run tailorswif assemble         # cut it together
uv run tailorswif rank             # ranking UI at :8765 — keys 1 / 2 / 3 / s
uv run tailorswif results          # Elo, plus averages by model and staging
```

To render for real you need a [fal.ai](https://fal.ai) key — pay-as-you-go, no
subscription, and what a real pipeline would be built against. Stay on the free
tier and buy $25 of one-time credits; the Agent subscriptions do not discount
API calls.

```bash
export FAL_KEY=...
uv run tailorswif run --provider fal --budget 15
uv run tailorswif assemble --audio some-track.mp3
```

Add `--mode grid` to any command to run the original variant instead: the same
single shot across 3 models × 4 stagings, cleaner as an experiment, no artifact.

## What assembly does

Two things, and the second matters more than it sounds. It **trims the handles**
— half a second off each end, where generated clips are least stable — and it
**grades everything to match**. Twelve separately generated clips come back with
different colour and contrast, and that inconsistency is the loudest signal that
a video was assembled rather than shot. Run `--no-grade` once to see how much
work it is doing.

## What comes out

1. **A ~50 second video** you can put in front of someone
2. **Whether the shots hold together** as one place — the thing a single-shot
   test cannot tell you
3. **Which model** holds a restrained, photographic register
4. **Whether deadpan is reachable** through blocking
5. **Preference labels** — the seed of the only asset here that compounds

Ranking is pairwise, never absolute scores. Absolute multi-dimension scores from
a VLM are correlated and uncalibrated, and the axis that matters — *does this
read as intentional or as random* — has the least signal in any public
preference data. You are the reward model at MVP.

## Layout

```
src/tailorswif/
  schemas.py      RealityRule (invariants required), ShotSpec, Staging
  banned.py       negative-concept bank + dreamlike-word guard
  staging.py      the four strategies under test
  sequence.py     the twelve shots, the world, the escalation
  experiment.py   the single-shot grid, and the shared reality rule
  assemble.py     trim, normalise, grade to match, concatenate
  providers/      base (budget guard, catalog), dryrun, fal
  ledger.py       sqlite — takes, comparisons, generations-per-usable-shot
  rank.py         pairwise Elo
  web.py          the ranking UI
```

## Two things enforced in code, not by convention

**Every request is priced before dispatch** and checked against a ceiling
(`providers/base.py`). Video inference has no checkpointing and no salvage value
when a render is rejected, so the guard sits in front of the call.

**Native audio is off everywhere.** We have a song, and audio roughly doubles the
per-second rate on several models.

## The one metric

`generations per usable shot`, printed by `results`. Not the per-second rate —
that ratio is what decides the bill. Documented productions run it at **5–9**;
under **2** is the target, and the entire justification for gating early.

## Kill criteria

Stated in advance so they are not rationalised away later:

- Nothing good across all twelve → the register is not reachable with today's
  tools. Wait, or go straight at compositing and splatting instead.
- The cut does not read as one street → world consistency needs the lookbook and
  reference layer before anything else gets built.
- `faces_primary` wins → the deadpan-through-blocking thesis is wrong and the
  cinematography layer needs rethinking.
- It looks good **and** staging made no difference → a prompt is enough, and the
  directing layer is not the differentiator. That is the result worth taking
  most seriously.

## Not built yet, on purpose

Music analysis, the creative director, the world bible, the critic, keyframe-first
rendering, compositing, splatting. All of it waits on the answer to this run.

The splat spike is the other half of the question and is not here yet: it is the
only capability on the roadmap that someone with a Veo subscription and a good
prompt cannot reproduce.
