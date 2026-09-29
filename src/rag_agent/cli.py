"""Command-line delivery, checks, and measured reporting."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import statistics
import time
from pathlib import Path
from typing import Annotated, Any

import typer

from rag_agent.config import Settings
from rag_agent.logging_setup import configure_logging
from rag_agent.schemas import Answer

app = typer.Typer(
    help="Ingest a public website and ask source-grounded questions.", no_args_is_help=True
)


@app.callback()
def main() -> None:
    """Use JSON event logging without logging question or source text."""
    configure_logging("WARNING")


def _settings(**overrides: Any) -> Settings:
    try:
        return Settings(**overrides)
    except Exception:
        typer.echo("Invalid configuration. Check .env and the documented settings.", err=True)
        raise typer.Exit(2) from None


def _agent(settings: Settings) -> Any:
    try:
        from rag_agent.graph import Agent

        return Agent(settings)
    except FileNotFoundError:
        typer.echo("No index found. Run 'rag ingest' first.", err=True)
        raise typer.Exit(2) from None
    except Exception as exc:
        typer.echo(f"Cannot load the index ({type(exc).__name__}). Run 'rag doctor'.", err=True)
        raise typer.Exit(1) from None


def _json(value: Any) -> None:
    typer.echo(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def _answer(agent: Any, question: str, use_cache: bool = True) -> Answer:
    try:
        return Answer.model_validate(agent.ask(question, use_cache=use_cache))
    except Exception as exc:
        typer.echo(f"The query could not be completed ({type(exc).__name__}).", err=True)
        raise typer.Exit(1) from None


def _print_answer(result: Answer, show_context: bool = False) -> None:
    typer.echo(result.answer)
    for index, source in enumerate(result.sources, 1):
        typer.echo(f"\n[{index}] {source.title}\n{source.url}")
        if show_context:
            typer.echo(source.evidence)
    typer.echo(
        f"\nEstimated new cost: ${result.usage.estimated_usd:.6f}; cached: {str(result.cached).lower()}"
    )


@app.command("ingest")
def ingest_command(
    start_url: Annotated[
        str | None, typer.Option(help="Public seed URL; must obey ALLOWED_PREFIX.")
    ] = None,
    max_pages: Annotated[int | None, typer.Option(min=1, max=500)] = None,
    force: Annotated[
        bool, typer.Option(help="Rebuild the index even if a current index exists.")
    ] = False,
    dry_run: Annotated[
        bool, typer.Option(help="Crawl and inspect without replacing the index.")
    ] = False,
) -> None:
    """Crawl, extract, chunk, embed, and atomically persist a website."""
    from rag_agent.ingest import ingest

    overrides: dict[str, Any] = {}
    if start_url is not None:
        overrides["start_url"] = start_url
    if max_pages is not None:
        overrides["max_pages"] = max_pages
    try:
        _json(asyncio.run(ingest(_settings(**overrides), force=force, dry_run=dry_run)))
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(
            f"Ingestion failed ({type(exc).__name__}). Existing data has not been intentionally deleted.",
            err=True,
        )
        raise typer.Exit(1) from None


@app.command("ask")
def ask_command(
    question: Annotated[str, typer.Argument(help="Question about the indexed website.")],
    json_output: Annotated[
        bool, typer.Option("--json", help="Return the complete typed JSON response.")
    ] = False,
    show_context: Annotated[
        bool, typer.Option(help="Include the exact supporting passages.")
    ] = False,
) -> None:
    """Answer one question with verified source URLs."""
    result = _answer(_agent(_settings()), question)
    if json_output:
        _json(result.model_dump(mode="json"))
    else:
        _print_answer(result, show_context)


@app.command("chat")
def chat_command() -> None:
    """Ask independent grounded questions interactively; enter /quit to exit."""
    agent = _agent(_settings())
    typer.echo("Website chat. Enter /quit to exit. Each question uses the indexed corpus.")
    while True:
        try:
            question = typer.prompt("Question", prompt_suffix="> ")
        except (EOFError, KeyboardInterrupt, typer.Abort):
            break
        if question.strip().lower() in {"/quit", "/exit", "quit", "exit"}:
            break
        if question.strip():
            _print_answer(_answer(agent, question))


@app.command("stats")
def stats_command() -> None:
    """Print index and retrieval statistics as JSON."""
    _json(_agent(_settings()).stats())


@app.command("doctor")
def doctor_command() -> None:
    """Inspect configuration and dependency availability without paid calls."""
    settings = _settings()
    modules = ["langgraph", "chromadb", "sentence_transformers", "fastapi", "typer"]
    checks = {module: importlib.util.find_spec(module) is not None for module in modules}
    _json(
        {
            "provider": settings.provider,
            "embedding_id": settings.embedding_id,
            "data_dir": str(settings.data_dir.resolve()),
            "data_exists": settings.data_dir.exists(),
            "api_auth_enabled": settings.api_token is not None,
            "dependencies": checks,
            "note": "Index compatibility and model availability are checked when loading the agent.",
        }
    )
    if not all(checks.values()):
        raise typer.Exit(1)


@app.command("eval")
def eval_command(
    questions: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "evaluation/questions.json"
    ),
    out: Annotated[Path, typer.Option(help="Directory for measured evaluation artifacts.")] = Path(
        "evaluation/results"
    ),
) -> None:
    """Measure source coverage, refusal, citation checks, cost, and latency."""
    from evaluation.run_eval import run_evaluation

    _json(run_evaluation(_settings(), questions, out))


@app.command("cost-report")
def cost_report_command(
    report: Annotated[Path, typer.Option(exists=True, dir_okay=False)] = Path(
        "evaluation/results/results.json"
    ),
    out: Annotated[Path, typer.Option(dir_okay=False)] = Path("COST_ANALYSIS.md"),
) -> None:
    """Generate a cost analysis from measured evaluation results."""
    from evaluation.reporting import generate_cost_report

    data = json.loads(report.read_text(encoding="utf-8"))
    generate_cost_report(data, out)
    typer.echo(str(out.resolve()))


@app.command("bench")
def bench_command(
    runs: Annotated[int, typer.Option(min=1, max=1000)] = 30,
    out: Annotated[Path, typer.Option(dir_okay=False)] = Path("artifacts/benchmark.json"),
) -> None:
    """Measure repeated uncached queries and aggregate actual stage timings."""
    agent = _agent(_settings())
    questions = [
        "How can I create a Python list?",
        "How does a for loop work?",
        "How do I define a function?",
        "How do I handle exceptions?",
        "What are Python dictionaries?",
        "How do I read and write files?",
    ]
    elapsed: list[float] = []
    stages: dict[str, list[float]] = {}
    total_cost = 0.0
    for index in range(runs):
        started = time.perf_counter()
        result = _answer(agent, questions[index % len(questions)], use_cache=False)
        elapsed.append((time.perf_counter() - started) * 1000)
        total_cost += result.usage.estimated_usd
        for name, value in result.timings_ms.items():
            stages.setdefault(name, []).append(value)

    def summary(values: list[float]) -> dict[str, float]:
        ordered = sorted(values)
        return {
            "mean_ms": statistics.mean(values),
            "p50_ms": statistics.median(values),
            "p95_ms": ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))],
        }

    data = {
        "runs": runs,
        "unique_questions": len(set(questions[:runs])),
        "cache_enabled": False,
        "total": summary(elapsed),
        "stages": {name: summary(values) for name, values in stages.items()},
        "estimated_usd": total_cost,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    _json(data)


@app.command("diagram")
def diagram_command(
    out: Annotated[Path, typer.Option(dir_okay=False)] = Path("docs/langgraph.mmd"),
) -> None:
    """Export the actual compiled query graph as Mermaid."""
    agent = _agent(_settings())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(agent.graph.get_graph().draw_mermaid(), encoding="utf-8")
    typer.echo(str(out.resolve()))


@app.command("smoke")
def smoke_command() -> None:
    """Verify four tutorial questions and one unsupported question against the index."""
    agent = _agent(_settings())
    questions = [
        ("How can I create a Python list?", True),
        ("How do I define a function?", True),
        ("How do I handle exceptions?", True),
        ("What are Python dictionaries?", True),
        ("What is the current weather in Tokyo?", False),
    ]
    results = []
    for question, expected in questions:
        result = _answer(agent, question, use_cache=False)
        passed = result.answerable == expected and (not expected or bool(result.sources))
        results.append(
            {
                "question": question,
                "expected_answerable": expected,
                "answerable": result.answerable,
                "sources": len(result.sources),
                "passed": passed,
            }
        )
    _json({"passed": all(item["passed"] for item in results), "results": results})
    if not all(item["passed"] for item in results):
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
