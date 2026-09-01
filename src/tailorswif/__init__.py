"""tailorswif - controlled surrealism, phase 0.

Nothing here generates a music video yet, on purpose. This is the Deadpan Test:
the smallest experiment that answers whether the target register is reachable
with current models, and the ranking tool that turns your judgement into data.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .banned import ConceptRejected
from .experiment import EXPERIMENT_NAME, matrix, pair_count
from .ledger import Ledger
from .providers.base import CATALOG, Budget, BudgetExceeded
from .rank import CRITERIA, elo, group_ratings
from .web import serve

__all__ = ["main"]

DEFAULT_LEDGER = "runs/ledger.sqlite"
DEFAULT_ROOT = "runs"


def _provider(name: str):
    if name == "dryrun":
        from .providers.dryrun import DryRunProvider

        return DryRunProvider()
    if name == "fal":
        from .providers.fal import FalProvider

        return FalProvider()
    raise SystemExit(f"unknown provider: {name}")


def cmd_plan(args: argparse.Namespace) -> int:
    """Print the full matrix and what it would cost. Spends nothing."""
    total = 0.0
    for model_key, shot in matrix():
        spec = CATALOG[model_key]
        cost = spec.price(shot.render_duration_s)
        total += cost
        print(f"\n\033[1m{model_key} / {shot.staging.key}\033[0m  "
              f"{shot.render_duration_s:.0f}s  ${cost:.2f}")
        print(f"  {shot.staging.label}")
        print(f"  {shot.prompt()}")
    n = len(matrix())
    print(f"\n{n} takes, {pair_count(n)} comparisons, ${total:.2f} to run.")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    ledger = Ledger(args.ledger)
    provider = _provider(args.provider)
    budget = Budget(ceiling_usd=args.budget)
    root = Path(args.root) / EXPERIMENT_NAME

    ok = failed = 0
    for model_key, shot in matrix():
        spec = CATALOG[model_key]
        take_id = f"{EXPERIMENT_NAME}.{model_key}.{shot.staging.key}"
        out = root / f"{take_id}.mp4"
        if out.exists() or out.with_suffix(".txt").exists():
            print(f"skip  {take_id} (already rendered)")
            continue

        quote = spec.price(shot.render_duration_s)
        try:
            budget.reserve(quote)
        except BudgetExceeded as exc:
            print(f"\nstopped: {exc}")
            break

        print(f"gen   {take_id}  ${quote:.2f} ... ", end="", flush=True)
        try:
            actual = provider.generate(
                spec=spec,
                prompt=shot.prompt(),
                duration_s=shot.render_duration_s,
                out_path=str(out),
            )
        except Exception as exc:  # provider failures must not lose the run
            budget.release(quote)
            failed += 1
            print(f"failed: {exc}")
            ledger.record_take(
                take_id=take_id, shot_id=shot.shot_id, experiment=EXPERIMENT_NAME,
                provider=provider.name, model=model_key, prompt=shot.prompt(),
                staging=shot.staging.key, status="failed", reject_reason=str(exc)[:200],
            )
            continue

        budget.settle(quote, actual)
        ok += 1
        print(f"ok  (${actual:.2f})")
        ledger.record_take(
            take_id=take_id, shot_id=shot.shot_id, experiment=EXPERIMENT_NAME,
            provider=provider.name, model=model_key, prompt=shot.prompt(),
            staging=shot.staging.key, path=str(out), cost_usd=actual, status="ok",
        )

    print(f"\n{ok} ok, {failed} failed, ${budget.spent_usd:.2f} spent "
          f"of ${budget.ceiling_usd:.2f}")
    if ok:
        print(f"next: uv run tailorswif rank   ({pair_count(ok)} comparisons)")
    return 0


def cmd_rank(args: argparse.Namespace) -> int:
    serve(
        Ledger(args.ledger),
        EXPERIMENT_NAME,
        criterion=args.criterion,
        root=args.root,
        port=args.port,
    )
    return 0


def cmd_results(args: argparse.Namespace) -> int:
    ledger = Ledger(args.ledger)
    stats = ledger.stats(EXPERIMENT_NAME)
    triples = [
        (c["left_id"], c["right_id"], c["winner_id"])
        for c in ledger.comparisons(EXPERIMENT_NAME)
        if c["criterion"] == args.criterion
    ]
    take_ids = [r["take_id"] for r in ledger.takes(EXPERIMENT_NAME)]
    rated = elo(triples, take_ids=take_ids)

    print(f"\n\033[1m{EXPERIMENT_NAME}\033[0m  {args.criterion}")
    print(f"{stats.takes} takes, {stats.usable} usable, ${stats.spend_usd:.2f} spent")
    ratio = stats.generations_per_usable_shot
    print(f"generations per usable shot: {ratio if ratio else '-'}   (target < 2)\n")

    if not triples:
        print("no comparisons yet - run `uv run tailorswif rank`")
        return 0

    for r in rated:
        print(f"  {r.rating:7.0f}  {r.take_id}   {r.wins}-{r.losses}-{r.draws}")
    for label, key in (("by model", "model"), ("by staging", "staging")):
        grouped = group_ratings(rated, key)
        if grouped:
            print(f"\n  \033[1m{label}\033[0m")
            for name, value in grouped.items():
                print(f"    {value:7.0f}  {name}")
    print()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="tailorswif", description="Deadpan Test - phase 0"
    )
    parser.add_argument("--ledger", default=DEFAULT_LEDGER)
    parser.add_argument("--root", default=DEFAULT_ROOT)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("plan", help="print the matrix and its cost, spend nothing")

    run = sub.add_parser("run", help="render the matrix")
    run.add_argument("--provider", default="dryrun", choices=("dryrun", "fal"))
    run.add_argument("--budget", type=float, default=60.0, help="USD ceiling")

    rank = sub.add_parser("rank", help="open the pairwise ranking UI")
    rank.add_argument("--criterion", default="overall", choices=tuple(CRITERIA))
    rank.add_argument("--port", type=int, default=8765)

    results = sub.add_parser("results", help="print Elo and the key ratio")
    results.add_argument("--criterion", default="overall", choices=tuple(CRITERIA))

    args = parser.parse_args()
    handler = {
        "plan": cmd_plan, "run": cmd_run, "rank": cmd_rank, "results": cmd_results
    }[args.cmd]
    try:
        return handler(args)
    except ConceptRejected as exc:
        print(f"concept rejected - {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
