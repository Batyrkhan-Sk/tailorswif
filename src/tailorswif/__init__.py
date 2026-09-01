"""tailorswif - controlled surrealism, phase 0.

Nothing here generates a full music video yet, on purpose. This builds one
short sequence - twelve shots, one world, one escalation - and gives you the
tools to judge it. The point is to find out whether the register is reachable
before committing to a pipeline, and to end up with something you can show
someone rather than only a finding.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import sequence as seq
from . import traverse as trv
from .assemble import build
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


# sequence and traverse expose the same surface, so the CLI treats them
# interchangeably. grid is the odd one out: same shot, many treatments, no cut.
CUTS = {
    "sequence": (seq, seq.SEQUENCE_NAME, seq.SEQUENCE_MODEL),
    "traverse": (trv, trv.TRAVERSE_NAME, trv.TRAVERSE_MODEL),
}


def _jobs(mode: str) -> list[tuple[str, object]]:
    return CUTS[mode][0].plan() if mode in CUTS else matrix()


def _run_name(mode: str) -> str:
    return CUTS[mode][1] if mode in CUTS else EXPERIMENT_NAME


def _take_id(mode: str, model: str, shot) -> str:
    if mode in CUTS:
        return f"{_run_name(mode)}.{model}.{shot.order:02d}"
    return f"{EXPERIMENT_NAME}.{model}.{shot.staging.key}"


# --------------------------------------------------------------------------- #


def cmd_plan(args: argparse.Namespace) -> int:
    """Print what would be rendered and what it costs. Spends nothing."""
    jobs = _jobs(args.mode)
    total = sum(
        CATALOG[m].price(s.render_duration_s) for m, s in jobs
    )

    if args.mode in CUTS:
        mod, name, _ = CUTS[args.mode]
        print(f"\n\033[1m{name}\033[0m  "
              f"{len(mod.SHOTS)} shots, {mod.runtime_s():.0f}s cut\n")
        for shot in mod.SHOTS:
            flags = " +probe" if shot.order in mod.PROBE_ORDERS else ""
            if shot.render_risk >= 3:
                flags += " \033[33m!risky\033[0m"
            print(f"  {shot.order:02d}  int {shot.intensity}  "
                  f"{shot.duration_s:>4.1f}s  {shot.staging.key:<18}{flags}")
            print(f"      {shot.anomaly or '(no anomaly - the world behaving)'}")
        if args.verbose:
            print("\n  --- prompts ---")
            for shot in mod.SHOTS:
                print(f"\n  [{shot.order:02d}] {shot.prompt()}")
    else:
        for model, shot in jobs:
            print(f"\n\033[1m{model} / {shot.staging.key}\033[0m  "
                  f"{shot.render_duration_s:.0f}s")
            print(f"  {shot.prompt()}")

    n = len(jobs)
    print(f"\n{n} renders, ${total:.2f} to run.")
    if args.mode in CUTS:
        mod = CUTS[args.mode][0]
        print(f"{len(mod.PROBE_ORDERS) * len(mod.PROBE_MODELS)} of those are "
              f"probes on {', '.join(mod.PROBE_MODELS)} for the model comparison.")
        risky = [s.order for s in mod.SHOTS if s.render_risk >= 3]
        if risky:
            print(f"shot {', '.join(str(o) for o in risky)} is high-risk to "
                  f"render - budget extra takes for it.")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    ledger = Ledger(args.ledger)
    provider = _provider(args.provider)
    budget = Budget(ceiling_usd=args.budget)
    name = _run_name(args.mode)
    root = Path(args.root) / name

    jobs = _jobs(args.mode)
    if args.only:
        wanted = set(args.only)
        jobs = [(m, s) for m, s in jobs if getattr(s, "order", None) in wanted]
        if not jobs:
            print(f"no shots matching {sorted(wanted)}", file=sys.stderr)
            return 2

    ok = failed = 0
    for model, shot in jobs:
        spec = CATALOG[model]
        take_id = _take_id(args.mode, model, shot)
        out = root / f"{take_id}.mp4"
        if out.exists() or out.with_suffix(".txt").exists():
            print(f"skip  {take_id}")
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
        except Exception as exc:  # a provider failure must not lose the run
            budget.release(quote)
            failed += 1
            print(f"failed: {exc}")
            ledger.record_take(
                take_id=take_id, shot_id=shot.shot_id, experiment=name,
                provider=provider.name, model=model, prompt=shot.prompt(),
                staging=shot.staging.key, status="failed",
                reject_reason=str(exc)[:200],
            )
            continue

        budget.settle(quote, actual)
        ok += 1
        print(f"ok  (${actual:.2f})")
        ledger.record_take(
            take_id=take_id, shot_id=shot.shot_id, experiment=name,
            provider=provider.name, model=model, prompt=shot.prompt(),
            staging=shot.staging.key, path=str(out), cost_usd=actual, status="ok",
        )

    print(f"\n{ok} ok, {failed} failed, ${budget.spent_usd:.2f} of "
          f"${budget.ceiling_usd:.2f}")
    if ok and args.mode in CUTS:
        print(f"next: uv run tailorswif --mode {args.mode} assemble")
    elif ok:
        print(f"next: uv run tailorswif rank   ({pair_count(ok)} comparisons)")
    return 0


def cmd_assemble(args: argparse.Namespace) -> int:
    """Cut the sequence: trim handles, normalise, grade to match, concatenate."""
    if args.mode not in CUTS:
        print("assemble needs --mode sequence or --mode traverse "
              "(the grid is the same shot many ways, it does not cut together)",
              file=sys.stderr)
        return 2
    mod, name, default_model = CUTS[args.mode]
    model = args.model or default_model
    root = Path(args.root) / name
    shots = mod.SHOTS
    if args.only:
        wanted = set(args.only)
        shots = [s for s in shots if s.order in wanted]
        if not shots:
            print(f"no shots matching {sorted(wanted)}", file=sys.stderr)
            return 2
    clips = [
        (root / f"{name}.{model}.{shot.order:02d}.mp4", shot.duration_s)
        for shot in shots
    ]
    missing = [p.name for p, _ in clips if not p.exists()]
    if missing:
        print(f"missing {len(missing)} of {len(clips)} clips:", file=sys.stderr)
        for missing_name in missing[:5]:
            print(f"  {missing_name}", file=sys.stderr)
        if len(missing) > 5:
            print(f"  ... and {len(missing) - 5} more", file=sys.stderr)

    out = Path(args.out or (Path(args.root) / f"{name}.mp4"))
    try:
        built = build(
            clips, out,
            handles_s=0.5,
            grade=not args.no_grade,
            audio=Path(args.audio) if args.audio else None,
            transition=args.transition,
            xfade_s=args.xfade,
        )
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"assemble failed: {exc}", file=sys.stderr)
        return 1

    size_mb = built.stat().st_size / 1e6
    print(f"\n{built}  ({size_mb:.1f} MB)")
    print(f"open it, then: uv run tailorswif --mode {args.mode} rank")
    return 0


def cmd_rank(args: argparse.Namespace) -> int:
    serve(
        Ledger(args.ledger),
        _run_name(args.mode),
        criterion=args.criterion,
        root=args.root,
        port=args.port,
    )
    return 0


def cmd_results(args: argparse.Namespace) -> int:
    ledger = Ledger(args.ledger)
    name = _run_name(args.mode)
    stats = ledger.stats(name)
    triples = [
        (c["left_id"], c["right_id"], c["winner_id"])
        for c in ledger.comparisons(name)
        if c["criterion"] == args.criterion
    ]
    take_ids = [r["take_id"] for r in ledger.takes(name)]
    rated = elo(triples, take_ids=take_ids)

    print(f"\n\033[1m{name}\033[0m  {args.criterion}")
    print(f"{stats.takes} takes, {stats.usable} usable, ${stats.spend_usd:.2f} spent")
    ratio = stats.generations_per_usable_shot
    print(f"generations per usable shot: {ratio or '-'}   (target < 2)\n")

    if not triples:
        print("no comparisons yet - run `uv run tailorswif rank`")
        return 0

    for r in rated:
        print(f"  {r.rating:7.0f}  {r.take_id}   {r.wins}-{r.losses}-{r.draws}")
    for label, key in (("by model", "model"), ("by staging", "staging")):
        if grouped := group_ratings(rated, key):
            print(f"\n  \033[1m{label}\033[0m")
            for gk, gv in grouped.items():
                print(f"    {gv:7.0f}  {gk}")
    print()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="tailorswif", description="Controlled surrealism - phase 0"
    )
    parser.add_argument("--ledger", default=DEFAULT_LEDGER)
    parser.add_argument("--root", default=DEFAULT_ROOT)
    parser.add_argument(
        "--mode", default="sequence", choices=("sequence", "traverse", "grid"),
        help="sequence: one altered law, one street, escalating (default). "
             "traverse: one figure through twelve spaces, tonal not ruled. "
             "grid: the same shot across models x staging, no cut.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    plan = sub.add_parser("plan", help="print the shot list and cost, spend nothing")
    plan.add_argument("-v", "--verbose", action="store_true", help="show full prompts")

    run = sub.add_parser("run", help="render")
    run.add_argument("--provider", default="dryrun", choices=("dryrun", "fal"))
    run.add_argument("--budget", type=float, default=25.0, help="USD ceiling")
    run.add_argument(
        "--only", type=int, nargs="+", metavar="N",
        help="render only these shot numbers. Use it to smoke-test one cheap "
             "shot before committing to the whole run - a wrong endpoint or "
             "payload then costs cents instead of eighteen failures.",
    )

    asm = sub.add_parser("assemble", help="cut the sequence together")
    asm.add_argument("--model", default=None)
    asm.add_argument("--out", default=None)
    asm.add_argument("--audio", default=None, help="optional music track")
    asm.add_argument("--no-grade", action="store_true",
                     help="skip the matching grade (to see how much it does)")
    asm.add_argument("--only", type=int, nargs="+", metavar="N",
                     help="cut only these shots - use it to look at one "
                          "transition on its own")
    asm.add_argument("--transition", default="cut", choices=("cut", "dissolve"),
                     help="cut is right for a threshold transition; dissolve "
                          "is here to compare against")
    asm.add_argument("--xfade", type=float, default=0.5,
                     help="dissolve length in seconds")

    rank = sub.add_parser("rank", help="open the pairwise ranking UI")
    rank.add_argument("--criterion", default="overall", choices=tuple(CRITERIA))
    rank.add_argument("--port", type=int, default=8765)

    results = sub.add_parser("results", help="print Elo and the key ratio")
    results.add_argument("--criterion", default="overall", choices=tuple(CRITERIA))

    args = parser.parse_args()
    handler = {
        "plan": cmd_plan, "run": cmd_run, "assemble": cmd_assemble,
        "rank": cmd_rank, "results": cmd_results,
    }[args.cmd]
    try:
        return handler(args)
    except ConceptRejected as exc:
        print(f"concept rejected - {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
