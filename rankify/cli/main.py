"""The `rankify` command. See CLI.md in this folder for the reference."""

import json
import sys
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from rankify import store
from rankify.service import NothingToAsk, Rankify, RankifyError, RankingView, RoundView

DEFAULT_DB = Path.home() / ".rankify" / "rankify.db"
EXIT_NOTHING_TO_ASK = 3

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Rank anything with a few decisive rounds.",
)

JsonOpt = Annotated[bool, typer.Option("--json", help="Print JSON for scripts and agents.")]
JudgeOpt = Annotated[str, typer.Option("--judge", help="Who is answering.")]
Slug = Annotated[str, typer.Argument(help="The list's short name, like 'nba'.")]


@app.callback()
def main(
    ctx: typer.Context,
    db: Annotated[
        Path, typer.Option("--db", envvar="RANKIFY_DB", help="SQLite file holding all data.")
    ] = DEFAULT_DB,
) -> None:
    ctx.obj = db


def _service(ctx: typer.Context, judge: str = "me") -> Rankify:
    return Rankify(store.connect(ctx.obj), judge=judge)


def _fail(message: str) -> NoReturn:
    typer.echo(f"error: {message}", err=True)
    raise typer.Exit(1)


def _emit_json(data) -> None:
    typer.echo(json.dumps(data, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------- lists and items


@app.command()
def new(
    ctx: typer.Context,
    slug: Slug,
    title: Annotated[str, typer.Argument(help="A readable title.")],
    items: Annotated[
        Path | None, typer.Option("--items", help="Text file with one item per line.")
    ] = None,
    mode: Annotated[str, typer.Option("--mode", help="quick, stable or exact.")] = "stable",
    method: Annotated[
        str,
        typer.Option(
            "--method",
            help="rankify, or a method to benchmark against: elo, elo-close, glicko2, "
            "trueskill, openskill, arena, just-sort-it, insertion-sort.",
        ),
    ] = "rankify",
    seed: Annotated[int | None, typer.Option("--seed", help="Fix the random seed.")] = None,
) -> None:
    """Make a new list."""
    names = items.read_text(encoding="utf-8").splitlines() if items else []
    try:
        _service(ctx).create_list(slug, title, names, mode=mode, method=method, seed=seed)
    except RankifyError as e:
        _fail(str(e))
    count = len([n for n in names if n.strip()])
    typer.echo(f"Made '{slug}' with {count} item{'s' if count != 1 else ''}.")


@app.command()
def add(
    ctx: typer.Context,
    slug: Slug,
    name: Annotated[str, typer.Argument(help="The item to add.")],
    note: Annotated[str | None, typer.Option("--note", help="A note for yourself.")] = None,
) -> None:
    """Add an item to a list."""
    try:
        _service(ctx).add_item(slug, name, note)
    except RankifyError as e:
        _fail(str(e))
    typer.echo(f"Added '{name}'.")


@app.command()
def remove(
    ctx: typer.Context,
    slug: Slug,
    name: Annotated[str, typer.Argument(help="The item to remove.")],
) -> None:
    """Hide an item from the ranking. Its answers still count."""
    try:
        _service(ctx).remove_item(slug, name)
    except RankifyError as e:
        _fail(str(e))
    typer.echo(f"Removed '{name}'.")


@app.command("lists")
def lists_(ctx: typer.Context, as_json: JsonOpt = False) -> None:
    """Show all lists."""
    rows = _service(ctx).lists()
    if as_json:
        _emit_json([r.__dict__ for r in rows])
        return
    if not rows:
        typer.echo('No lists yet. Make one with: rankify new <name> "Title"')
        return
    for r in rows:
        typer.echo(
            f"{r.list:<20} {r.items:>4} items  {r.answers:>5} answers  {r.mode:<6}  "
            f"{r.method:<14}  {r.title}"
        )


# ---------------------------------------------------------------- rounds


def _print_round(view: RoundView) -> None:
    typer.echo(f"Round {view.round} · {view.prompt}\n")
    for item in view.items:
        typer.echo(f"  {item.n}  {item.name}")
    numbers = " or ".join(str(i.n) for i in view.items)
    typer.echo(f"\nAnswer with: rankify answer {view.list} <{numbers}>   (or --cant-decide)")


def _round_json(view: RoundView) -> dict:
    return {
        "list": view.list,
        "round": view.round,
        "kind": view.kind,
        "prompt": view.prompt,
        "items": [{"n": i.n, "id": i.id, "name": i.name} for i in view.items],
        "rounds_left": None,  # the forecast arrives in Phase 4
    }


@app.command("next")
def next_(ctx: typer.Context, slug: Slug, as_json: JsonOpt = False, judge: JudgeOpt = "me") -> None:
    """Show the open round, or start a new one. Exits with code 3 when nothing is left to ask."""
    try:
        view = _service(ctx, judge).next_round(slug)
    except NothingToAsk as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(EXIT_NOTHING_TO_ASK) from None
    except RankifyError as e:
        _fail(str(e))
    if as_json:
        _emit_json(_round_json(view))
    else:
        _print_round(view)


@app.command()
def answer(
    ctx: typer.Context,
    slug: Slug,
    numbers: Annotated[
        list[int] | None, typer.Argument(help="Item numbers as shown, best first.")
    ] = None,
    cant_decide: Annotated[
        bool, typer.Option("--cant-decide", help="The items are too close to call.")
    ] = False,
    round_: Annotated[
        int | None, typer.Option("--round", help="Only answer if this round is still open.")
    ] = None,
    as_json: JsonOpt = False,
    judge: JudgeOpt = "me",
) -> None:
    """Answer the open round."""
    try:
        view = _service(ctx, judge).answer(slug, numbers, cant_decide=cant_decide, round_seq=round_)
    except RankifyError as e:
        _fail(str(e))
    if as_json:
        _emit_json({"list": view.list, "round": view.round, "saved": True})
    else:
        typer.echo(f"Saved round {view.round}.")


@app.command()
def undo(ctx: typer.Context, slug: Slug, as_json: JsonOpt = False, judge: JudgeOpt = "me") -> None:
    """Cancel your last answer and ask that round again."""
    try:
        view = _service(ctx, judge).undo(slug)
    except RankifyError as e:
        _fail(str(e))
    if as_json:
        _emit_json(_round_json(view))
    else:
        typer.echo("Undid the last answer. Asking it again:\n")
        _print_round(view)


# ---------------------------------------------------------------- results


def _ranking_json(view: RankingView) -> dict:
    return {
        "list": view.list,
        "title": view.title,
        "mode": view.mode,
        "method": view.method,
        "answers": view.answers,
        "target_reached": None,  # stopping rules arrive in Phase 2
        "position_bias": None if view.position_bias is None else round(view.position_bias, 1),
        "items": [
            {
                "rank": i.rank,
                "id": i.id,
                "name": i.name,
                "score": None if i.score is None else round(i.score, 1),
                "confidence": None if i.confidence is None else round(i.confidence, 4),
                "could_be": None if i.could_be is None else list(i.could_be),
            }
            for i in view.items
        ],
    }


def _print_ranking(view: RankingView) -> None:
    plural = "" if view.answers == 1 else "s"
    method = "" if view.method == "rankify" else f" · method {view.method}"
    typer.echo(f"{view.title} · {view.mode}{method} · {view.answers} answer{plural}\n")
    if not view.items:
        typer.echo("No items yet.")
        return
    width = max(4, *(len(i.name) for i in view.items))
    typer.echo(f" {'#':>3}  {'Item':<{width}}  {'Score':>5}  {'Confidence':>10}  Could be")
    for i in view.items:
        score = "" if i.score is None else f"{i.score:.0f}"
        conf = "" if i.confidence is None else f"{i.confidence:.0%}"
        could = ""
        if i.could_be is not None:
            lo, hi = i.could_be
            could = f"#{lo}" if lo == hi else f"#{lo}–#{hi}"
        typer.echo(f" {i.rank:>3}  {i.name:<{width}}  {score:>5}  {conf:>10}  {could}")


@app.command()
def show(ctx: typer.Context, slug: Slug, as_json: JsonOpt = False) -> None:
    """Show the current ranking."""
    try:
        view = _service(ctx).ranking(slug)
    except RankifyError as e:
        _fail(str(e))
    if as_json:
        _emit_json(_ranking_json(view))
    else:
        _print_ranking(view)


@app.command()
def verify(ctx: typer.Context, slug: Slug) -> None:
    """Rebuild the ranking from the answer log alone and compare it with what is stored."""
    try:
        problems = _service(ctx).verify(slug)
    except RankifyError as e:
        _fail(str(e))
    if problems:
        for p in problems:
            typer.echo(f"mismatch: {p}", err=True)
        raise typer.Exit(1)
    typer.echo("OK: the stored ranking matches a rebuild from the answer log.")


@app.command()
def bench(
    items: Annotated[str, typer.Option("--items", help="List sizes, comma-separated.")] = "10,20",
    judges: Annotated[
        str, typer.Option("--judges", help="human, perfect, noisy.")
    ] = "human,perfect",
    methods: Annotated[
        str, typer.Option("--methods", help="Methods to compare, comma-separated.")
    ] = "rankify,elo,elo-close,glicko2,trueskill,openskill,arena,just-sort-it,insertion-sort",
    runs: Annotated[int, typer.Option("--runs", help="Hidden lists per setting.")] = 20,
    budget: Annotated[
        int, typer.Option("--budget-per-item", help="Round budget per item in the list.")
    ] = 20,
    workers: Annotated[
        int, typer.Option("--workers", help="Parallel runs. Kept low so the machine stays cool.")
    ] = 2,
    report: Annotated[
        Path | None, typer.Option("--report", help="Also write the report to this file.")
    ] = None,
) -> None:
    """Benchmark rankify against rating systems, through this CLI, on hidden scores."""
    from rankify.bench import run_bench

    def progress(done: int, total: int) -> None:
        if done == total or done % max(1, total // 20) == 0:
            typer.echo(f"  {done}/{total} runs", err=True)

    text = run_bench(
        sizes=tuple(int(x) for x in items.split(",")),
        judges=tuple(judges.split(",")),
        methods=tuple(methods.split(",")),
        runs=runs,
        budget_per_item=budget,
        workers=workers,
        progress=progress,
    )
    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(text, encoding="utf-8")
    typer.echo(text)


if __name__ == "__main__":
    sys.exit(app())
