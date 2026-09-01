# tailorswif — phase 0

The **Deadpan Test**: the smallest experiment that answers whether the target
register is reachable with current models, plus the ranking tool that turns your
judgement into data.

This does not generate music videos. That is deliberate. The riskiest unknown is
not the pipeline — it is whether any current model can produce *one shot* that
would survive in a video of this class. Answer that for $10 before building
anything.

## What it does

One surreal beat — a parked car resting a metre above its space, on an ordinary
overcast street — rendered across **3 models × 4 staging strategies**. Then you
rank all 66 pairs by hand.

The four strategies vary two factors the architecture review argues are the real
levers on deadpan:

| | anomaly foregrounded | anomaly in background |
|---|---|---|
| **faces visible** | `faces_primary` | `faces_suppressed` |
| **no faces** | `backs_primary` | `backs_suppressed` |

Hypothesis: `backs_suppressed` wins and `faces_primary` looks like every other
AI video. Being wrong about that cheaply is the point.

## Run it

```bash
uv run tailorswif plan            # print the matrix and its cost, spend nothing
uv run tailorswif run             # dry run — writes prompt sidecars, costs $0
uv run tailorswif rank            # ranking UI at :8765 — keys 1 / 2 / 3 / s
uv run tailorswif results         # Elo, plus averages by model and by staging
```

To render for real you need a [fal.ai](https://fal.ai) key — pay-as-you-go, no
subscription, and it is what a real pipeline would be built against:

```bash
export FAL_KEY=...
uv run tailorswif run --provider fal --budget 15
```

**Cost: $9.98** for all twelve takes at 8s (6s + 1s handles each end).

## What comes out

Three answers and a dataset:

1. **Which model** can hold a restrained, photographic register at all
2. **Whether deadpan is reachable** through blocking, or collapses either way
3. **What a frame in this register looks like** when you get one
4. **66 preference labels** — the seed of the only asset here that compounds

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
  experiment.py   the matrix
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
  tools. Wait a year.
- `faces_primary` wins → the deadpan-through-blocking thesis is wrong and the
  cinematography layer needs rethinking.
- Everything looks like a stock video with a floating car → specificity is not
  transferring, and the problem is the prompt layer, not the model.

## Not built yet, on purpose

Music analysis, the creative director, the world bible, the critic, compositing,
splatting. All of it waits on the answer to this test.
