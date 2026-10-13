"""The `rankify` command. See CLI.md in this folder for the reference."""

import json
import sys
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from rankify import store
from rankify.service import (
    ForecastView,
    NothingToAsk,
    Rankify,
    RankifyError,
    RankingView,
    RoundView,
    tiers,
)

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
            "trueskill, openskill, arena, just-sort-it, insertion-sort, ford-johnson.",
        ),
    ] = "rankify",
    seed: Annotated[int | None, typer.Option("--seed", help="Fix the random seed.")] = None,
    calibrate: Annotated[
        bool,
        typer.Option(
            "--calibrate",
            help="Repeat some earlier pairs, sides swapped, so `rankify calibrate` can measure "
            "how you answer.",
        ),
    ] = False,
    rounds: Annotated[
        str,
        typer.Option(
            "--rounds",
            help="pairs: pairs only (the default). mixed: also 'pick the best' and 'put in "
            "order' rounds of 3 to 5 items, whichever teaches the most per second; it did not "
            "save time in the benchmark yet.",
        ),
    ] = "pairs",
    planner: Annotated[
        str,
        typer.Option(
            "--planner",
            hidden=True,
            help="Benchmark only: time (rankify), per-round, or closest.",
        ),
    ] = "time",
    as_json: JsonOpt = False,
) -> None:
    """Make a new list."""
    names = items.read_text(encoding="utf-8").splitlines() if items else []
    try:
        _service(ctx).create_list(
            slug,
            title,
            names,
            mode=mode,
            method=method,
            seed=seed,
            calibrate=calibrate,
            rounds=rounds,
            planner=planner,
        )
    except RankifyError as e:
        _fail(str(e))
    count = len([n for n in names if n.strip()])
    if as_json:
        _emit_json({"list": slug, "items": count, "made": True})
        return
    typer.echo(f"Made '{slug}' with {count} item{'s' if count != 1 else ''}.")


@app.command()
def add(
    ctx: typer.Context,
    slug: Slug,
    name: Annotated[str, typer.Argument(help="The item to add.")],
    note: Annotated[str | None, typer.Option("--note", help="A note for yourself.")] = None,
    as_json: JsonOpt = False,
) -> None:
    """Add an item to a list."""
    try:
        _service(ctx).add_item(slug, name, note)
    except RankifyError as e:
        _fail(str(e))
    if as_json:
        _emit_json({"list": slug, "added": name})
        return
    typer.echo(f"Added '{name}'.")


@app.command()
def remove(
    ctx: typer.Context,
    slug: Slug,
    name: Annotated[str, typer.Argument(help="The item to remove.")],
    as_json: JsonOpt = False,
) -> None:
    """Hide an item from the ranking. Its answers still count."""
    try:
        _service(ctx).remove_item(slug, name)
    except RankifyError as e:
        _fail(str(e))
    if as_json:
        _emit_json({"list": slug, "removed": name})
        return
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


def _print_round(view: RoundView, forecast: ForecastView | None = None) -> None:
    left = f" · {forecast.text()}" if forecast else ""
    typer.echo(f"Round {view.round}{left}\n{view.prompt}\n")
    for item in view.items:
        typer.echo(f"  {item.n}  {item.name}")
    if view.kind == "rank":
        example = " ".join(str(i.n) for i in reversed(view.items))
        how = f"<all numbers, best first, like {example}>"
    else:
        how = "<" + " or ".join(str(i.n) for i in view.items) + ">"
    typer.echo(f"\nAnswer with: rankify answer {view.list} {how}   (or --cant-decide)")


def _round_json(view: RoundView, forecast: ForecastView | None = None) -> dict:
    return {
        "list": view.list,
        "round": view.round,
        "kind": view.kind,
        "prompt": view.prompt,
        "items": [{"n": i.n, "id": i.id, "name": i.name} for i in view.items],
        "rounds_left": forecast.as_dict() if forecast else None,
    }


ModeOpt = Annotated[
    str | None, typer.Option("--mode", help="quick, stable or exact, for this session only.")
]


@app.command("next")
def next_(
    ctx: typer.Context,
    slug: Slug,
    as_json: JsonOpt = False,
    judge: JudgeOpt = "me",
    mode: ModeOpt = None,
    no_forecast: Annotated[
        bool,
        typer.Option(
            "--no-forecast", help="Skip the rounds-left estimate, which can take up to a second."
        ),
    ] = False,
) -> None:
    """Show the open round, or start a new one. Exits with code 3 when nothing is left to ask."""
    rk = _service(ctx, judge)
    try:
        view = rk.next_round(slug, mode=mode)
        forecast = None if no_forecast else rk.forecast(slug, mode)
    except NothingToAsk as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(EXIT_NOTHING_TO_ASK) from None
    except RankifyError as e:
        _fail(str(e))
    if as_json:
        _emit_json(_round_json(view, forecast))
    else:
        _print_round(view, forecast)


@app.command()
def forecast(
    ctx: typer.Context,
    slug: Slug,
    mode: ModeOpt = None,
    as_json: JsonOpt = False,
    judge: JudgeOpt = "me",
) -> None:
    """Estimate how many rounds are left until the mode's target, from the answers each pair
    the mode needs will take with this judge's habits."""
    try:
        f = _service(ctx, judge).forecast(slug, mode)
    except RankifyError as e:
        _fail(str(e))
    if as_json:
        _emit_json(
            None
            if f is None
            else {"list": f.list, "mode": f.mode, **f.as_dict(), "draws": f.draws, "ms": f.ms}
        )
        return
    if f is None:
        typer.echo("No forecast: only lists ranked by rankify's planner have one.")
        return
    typer.echo(f"{f.mode.capitalize()}: {f.text()} ({f.draws} draws, {f.ms:.0f} ms).")


@app.command()
def answer(
    ctx: typer.Context,
    slug: Slug,
    numbers: Annotated[
        list[int] | None,
        typer.Argument(
            help="Item numbers as shown: the better or best one, or for 'put in order' all of "
            "them best first (the last may be left out; 3142 works too)."
        ),
    ] = None,
    cant_decide: Annotated[
        bool, typer.Option("--cant-decide", help="The items are too close to call.")
    ] = False,
    round_: Annotated[
        int | None, typer.Option("--round", help="Only answer if this round is still open.")
    ] = None,
    as_json: JsonOpt = False,
    judge: JudgeOpt = "me",
    ms: Annotated[
        int | None,
        typer.Option("--ms", hidden=True, help="Answer time measured by the caller, in ms."),
    ] = None,
) -> None:
    """Answer the open round."""
    try:
        view = _service(ctx, judge).answer(
            slug, numbers, cant_decide=cant_decide, round_seq=round_, ms=ms
        )
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


def _ranking_json(view: RankingView, with_tiers: bool = False) -> dict:
    out = {
        "list": view.list,
        "title": view.title,
        "mode": view.mode,
        "method": view.method,
        "answers": view.answers,
        "target_reached": view.target_reached,
        "sigma": None if view.sigma is None else round(view.sigma, 3),
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
    if with_tiers:
        groups = tiers(view.items)
        if groups is not None:
            tier_of = {i.id: t for t, group in enumerate(groups, start=1) for i in group}
            for item in out["items"]:
                item["tier"] = tier_of[item["id"]]
    return out


def _print_ranking(view: RankingView) -> None:
    plural = "" if view.answers == 1 else "s"
    method = "" if view.method == "rankify" else f" · method {view.method}"
    status = {True: " · target reached", False: " · not there yet"}.get(view.target_reached, "")
    typer.echo(f"{view.title} · {view.mode}{method} · {view.answers} answer{plural}{status}\n")
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
def show(
    ctx: typer.Context,
    slug: Slug,
    as_json: JsonOpt = False,
    by_tier: Annotated[
        bool, typer.Option("--tiers", help="Group items into tiers whose order is settled.")
    ] = False,
) -> None:
    """Show the current ranking."""
    try:
        view = _service(ctx).ranking(slug)
    except RankifyError as e:
        _fail(str(e))
    if as_json:
        _emit_json(_ranking_json(view, with_tiers=by_tier))
    elif by_tier:
        _print_tiers(view)
    else:
        _print_ranking(view)


def _print_tiers(view: RankingView) -> None:
    groups = tiers(view.items)
    if groups is None:
        _fail(f"tiers need Confidence, which method {view.method} doesn't give")
    plural = "" if view.answers == 1 else "s"
    typer.echo(f"{view.title} · {view.mode} · {view.answers} answer{plural}\n")
    typer.echo(
        "A new tier starts where the item above is confidently better (90%). "
        "Inside a tier the order isn't settled yet.\n"
    )
    for t, group in enumerate(groups, start=1):
        ranks = f"#{group[0].rank}" if len(group) == 1 else f"#{group[0].rank}–#{group[-1].rank}"
        typer.echo(f" Tier {t} ({ranks}): " + ", ".join(i.name for i in group))


@app.command()
def export(
    ctx: typer.Context,
    slug: Slug,
    out: Annotated[
        Path | None, typer.Option("--out", help="Write to this file instead of the screen.")
    ] = None,
) -> None:
    """Write the list, its items and every round as JSON lines: a backup, and a log
    another rankify can read."""
    try:
        records = _service(ctx).export(slug)
    except RankifyError as e:
        _fail(str(e))
    text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
    if out is None:
        typer.echo(text, nl=False)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    rounds = sum(1 for r in records if "round" in r)
    typer.echo(f"Wrote {slug}: {len(records) - rounds - 1} items and {rounds} rounds to {out}.")


@app.command()
def rebuild(ctx: typer.Context, slug: Slug, as_json: JsonOpt = False) -> None:
    """Refit the list from its answer log with this version of rankify, and drop saved
    forecasts. Use it after an upgrade; it shows which items moved."""
    try:
        view = _service(ctx).rebuild(slug)
    except RankifyError as e:
        _fail(str(e))
    if as_json:
        _emit_json(view.as_dict())
        return
    before = view.engine_before or "none"
    typer.echo(
        f"Rebuilt {view.list} from {view.answers} answers with engine {view.engine_now} "
        f"(the last fit was made by {before}); dropped {view.forecasts_dropped} saved forecasts."
    )
    if not view.moved:
        typer.echo("The ranking didn't change.")
    for name, was, now in view.moved:
        typer.echo(f"  {name}: #{was} -> #{now}")


@app.command()
def verify(ctx: typer.Context, slug: Slug, as_json: JsonOpt = False) -> None:
    """Rebuild the ranking from the answer log alone and compare it with what is stored."""
    try:
        problems = _service(ctx).verify(slug)
    except RankifyError as e:
        _fail(str(e))
    if as_json:
        _emit_json({"list": slug, "ok": not problems, "problems": problems})
        if problems:
            raise typer.Exit(1)
        return
    if problems:
        for p in problems:
            typer.echo(f"mismatch: {p}", err=True)
        raise typer.Exit(1)
    typer.echo("OK: the stored ranking matches a rebuild from the answer log.")


@app.command()
def report(
    ctx: typer.Context,
    slug: Slug,
    fmt: Annotated[
        str, typer.Option("--format", help="md (Markdown) or json.", case_sensitive=False)
    ] = "md",
    as_json: JsonOpt = False,
    judge: JudgeOpt = "me",
) -> None:
    """A report for an agent: the ranking, ties, weak spots, slow decisions, upsets and the
    judge's habits."""
    from rankify.report import build, markdown

    if fmt.lower() not in ("md", "json"):
        _fail("--format must be md or json")
    try:
        data = build(_service(ctx, judge), slug)
    except RankifyError as e:
        _fail(str(e))
    if as_json or fmt.lower() == "json":
        _emit_json(data)
    else:
        typer.echo(markdown(data))


@app.command()
def why(
    ctx: typer.Context,
    slug: Slug,
    round_: Annotated[int, typer.Option("--round", help="The round to explain.")],
    as_json: JsonOpt = False,
) -> None:
    """Why rankify asked a round: what it expected to learn, and what else it considered."""
    try:
        view = _service(ctx).why(slug, round_)
    except RankifyError as e:
        _fail(str(e))
    if as_json:
        _emit_json(view.__dict__)
        return
    typer.echo(f"Round {view.round} · mode {view.mode} · {view.in_play} items still matter")
    t = view.timing
    pace = f"{t['base']:.1f} s per answer" + (
        f", +{t['close']:.1f} s on close calls" if t["close"] else ""
    )
    typer.echo(f"Expected answer time: {pace} (from {t['samples']} of your timed answers)\n")
    if view.chosen is None:
        typer.echo(f"Stopped: {view.reason}.")
    typer.echo(f"  {'Round':<52} {'Learns':>8} {'Time':>6}")
    for k, c in enumerate(view.candidates):
        mark = "→" if k == 0 and view.chosen is not None else " "
        kind = {"pair": "", "pick": "pick: ", "rank": "order: "}[c["kind"]]
        joiner = " vs " if c["kind"] == "pair" else ", "
        text = kind + joiner.join(c["names"])
        if len(text) > 52:
            text = text[:51] + "…"
        typer.echo(f"{mark} {text:<52} {c['gain']:>6.3f} b {c['seconds']:>5.1f}s")
    typer.echo(
        "\nLearns: expected bits about the order of the shown items, counting only the pairs "
        "that matter for the mode."
    )


@app.command()
def bench(
    items: Annotated[str, typer.Option("--items", help="List sizes, comma-separated.")] = "10,20",
    judges: Annotated[
        str,
        typer.Option(
            "--judges",
            help="human, perfect, noisy, sharp, normal, fuzzy, careless, biased, thurstone, "
            "similar, tired.",
        ),
    ] = "human,perfect",
    methods: Annotated[
        str, typer.Option("--methods", help="Methods to compare, comma-separated.")
    ] = "rankify,rankify-mixed,elo,elo-close,glicko2,trueskill,openskill,arena,just-sort-it,insertion-sort",
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
    set_time_scale: Annotated[
        float,
        typer.Option(
            "--set-time-scale",
            help="Multiply the judges' time on pick and rank rounds, such as 0.5 or 2, to see "
            "how much the result depends on that guess. Use a separate --cache per value.",
        ),
    ] = 1.0,
    judge_profile: Annotated[
        Path | None,
        typer.Option(
            "--judge-profile", help="Human judge settings from `rankify calibrate --out`."
        ),
    ] = None,
    cache: Annotated[
        Path | None,
        typer.Option(
            "--cache",
            help="Save each finished run here and skip runs already saved, so an interrupted "
            "benchmark resumes. Reuse only with the same code.",
        ),
    ] = None,
) -> None:
    """Benchmark rankify against rating systems, through this CLI, on hidden scores."""
    from rankify.bench import load_profile, run_bench

    profile = load_profile(judge_profile) if judge_profile else None

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
        profile=profile,
        cache=cache,
        set_time_scale=set_time_scale,
    )
    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(text, encoding="utf-8")
    typer.echo(text)


# ---------------------------------------------------------------- interactive play


PLAY_KEYS = (
    "[number] pick (to put in order, press the numbers best first)   [t] can't decide   "
    "[u] undo   [q] quit"
)


@app.command()
def play(
    ctx: typer.Context,
    slug: Slug,
    rounds: Annotated[
        int | None, typer.Option("--rounds", help="Stop after this many answers.")
    ] = None,
    judge: JudgeOpt = "me",
    mode: ModeOpt = None,
    plain: Annotated[
        bool,
        typer.Option(
            "--plain",
            help="Read keys line by line instead of opening the terminal UI. Used when input "
            "or output isn't a terminal.",
        ),
    ] = False,
) -> None:
    """Answer rounds in the terminal UI, timing each answer from question to last key.

    Stops by itself when the mode's target is reached or nothing is worth asking.
    """
    import sys
    import time

    rk = _service(ctx, judge)
    if not plain and sys.stdin.isatty() and sys.stdout.isatty():
        from rankify.tui import run

        try:
            rk.ranking(slug)  # fail early, with a plain message, on a missing list
        except RankifyError as e:
            _fail(str(e))
        answered = run(rk, slug, mode, rounds)
        typer.echo(
            f"{answered} answer{'s' if answered != 1 else ''} this session. "
            f"See the ranking with: rankify show {slug}"
        )
        return
    answered = 0
    typer.echo(f"{PLAY_KEYS}\n")
    while rounds is None or answered < rounds:
        try:
            view = rk.next_round(slug, mode=mode)
        except NothingToAsk as e:
            typer.echo(str(e))
            break
        except RankifyError as e:
            _fail(str(e))
        left = f" · {answered} answered" if answered else ""
        typer.echo(f"Round {view.round}{left} · {view.prompt}")
        for item in view.items:
            typer.echo(f"  {item.n}  {item.name}")
        shown = time.perf_counter()
        k = len(view.items)
        need = k - 1 if view.kind in ("pair", "rank") else 1  # a ranking's last is implied
        digits = [str(i) for i in range(1, k + 1)]
        typed: list[str] = []
        while True:
            key = typer.getchar().lower()
            if not key:  # end of input
                key, typed = "q", []
                break
            if key in ("t", "u", "q") and not typed:
                break
            if key in ("\x7f", "\b") and typed:  # backspace
                typed.pop()
                typer.echo("\b \b", nl=False)
            elif key in digits and key not in typed:
                typed.append(key)
                if view.kind == "rank":
                    typer.echo(key, nl=False)
                if len(typed) == need:
                    key = "".join(typed)
                    break
        if view.kind == "rank":
            typer.echo("")
        ms = int((time.perf_counter() - shown) * 1000)
        if key == "q":
            break
        if key == "u":
            try:
                rk.undo(slug)
                answered = max(0, answered - 1)
                typer.echo("  undone\n")
            except RankifyError as e:
                typer.echo(f"  {e}\n")
            continue
        if key == "t":
            rk.answer(slug, cant_decide=True, round_seq=view.round, ms=ms)
            typer.echo("  can't decide\n")
        else:
            numbers = [int(c) for c in key]
            rk.answer(slug, numbers, round_seq=view.round, ms=ms)
            if view.kind == "rank":
                rest = [i.n for i in view.items if i.n not in numbers]
                names = [view.items[x - 1].name for x in numbers + rest]
                typer.echo("  " + " > ".join(names) + "\n")
            else:
                typer.echo(f"  {view.items[numbers[0] - 1].name}\n")
        answered += 1
    typer.echo(
        f"{answered} answer{'s' if answered != 1 else ''} this session. "
        f"See the ranking with: rankify show {slug}"
    )


@app.command()
def calibrate(
    ctx: typer.Context,
    slugs: Annotated[
        list[str], typer.Argument(help="One or more lists to learn from, like 'travel food'.")
    ],
    out: Annotated[
        Path | None, typer.Option("--out", help="Write the judge profile (JSON) to this file.")
    ] = None,
    as_json: JsonOpt = False,
    judge: JudgeOpt = "me",
) -> None:
    """Estimate how you answer, from your rounds on one or more lists, for the benchmark's
    human judge. Pairs give accuracy, habits and pace; timed picks and orderings give how
    long sets take next to that pace."""
    from datetime import date

    try:
        profile = _service(ctx, judge).calibrate(slugs)
    except RankifyError as e:
        _fail(str(e))
    data = {
        "list": ",".join(slugs),
        "judge": judge,
        "date": date.today().isoformat(),
        **profile.as_dict(),
    }
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    if as_json:
        _emit_json(data)
        return
    p = profile
    dis = (
        "no repeated pairs"
        if p.repeat_disagreement is None
        else f"{p.repeat_disagreement:.0%} of {p.repeats} repeated pairs got a different answer "
        f"(the fit expects {p.repeat_disagreement_expected:.0%})"
    )
    used = set(p.measured)

    def tag(*keys: str) -> str:
        return "measured" if all(k in used for k in keys) else "shown only; keeps the guess"

    rows = [
        ("Neighbours told apart", f"{p.neighbour_accuracy:.0%} of the time", tag("score_spread")),
        ("Consistency", dis, "a check, not a setting"),
        ("Lean toward first item", f"{p.first_bonus:+.2f} (0 = none)", tag("first_bonus")),
        ("Random slips", f"{p.lapse:.0%} of answers", tag("lapse")),
        ("Can't decide", f"up to {p.tie_peak:.0%} on near-ties", tag("tie_peak")),
        ("Answer time, easy pairs", f"{p.base_seconds:.1f} s", tag("base_seconds")),
        ("Extra on close calls", f"+{p.close_seconds:.1f} s", tag("close_seconds")),
        ("Fatigue", f"noise +{p.fatigue:.1%} per round", tag("fatigue")),
        (
            "Picks and orderings",
            f"{p.set_time_scale:.2f} x the guessed time ({p.set_answers} timed)",
            tag("set_time_scale"),
        ),
    ]
    typer.echo(f"Judge profile for '{judge}' from {p.answers} answers on {p.items} items:\n")
    for label, value, status in rows:
        typer.echo(f"  {label:<24} {value:<46} ({status})")
    for note in p.notes:
        typer.echo(f"\n  note: {note}")
    if out:
        typer.echo(f"\nSaved to {out}. Use it with: rankify bench --judge-profile {out}")


if __name__ == "__main__":
    sys.exit(app())
