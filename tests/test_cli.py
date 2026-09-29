"""Offline CLI contracts: real command parsing, safe errors, and delivery outputs."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from rag_agent import cli
from rag_agent.config import Settings
from rag_agent.schemas import Answer, Citation, Usage

runner = CliRunner()
EVIDENCE = "A function definition uses the keyword def."
SOURCE = "https://docs.python.org/3/tutorial/controlflow.html"


class CLIAnswerAgent:
    """Fake only the offline agent boundary; exercise the production CLI unchanged."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []
        self.graph = SimpleNamespace(
            get_graph=lambda: SimpleNamespace(draw_mermaid=lambda: "graph TD; retrieve-->verify;")
        )

    def ask(self, question: str, use_cache: bool = True) -> Answer:
        self.calls.append((question, use_cache))
        answerable = "weather" not in question.lower()
        return Answer(
            answer="Functions introduce reusable behavior."
            if answerable
            else "Insufficient evidence.",
            answerable=answerable,
            sources=[
                Citation(url=SOURCE, title="Python functions", evidence=EVIDENCE, chunk_id="c1")
            ]
            if answerable
            else [],
            usage=Usage(input_tokens=5, output_tokens=4, estimated_usd=0.000001),
            timings_ms={"retrieval": 1.0, "generation": 2.0},
            request_id="cli-test-request",
        )

    def stats(self) -> dict[str, Any]:
        return {"pages": 12, "chunks": 80, "provider": "local"}


@pytest.fixture
def cli_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[Settings]:
    created: list[Settings] = []

    def factory(**overrides: Any) -> Settings:
        configured = Settings(
            _env_file=None,
            provider="local",
            data_dir=tmp_path / "data",
            api_token=None,
            **overrides,
        )
        created.append(configured)
        return configured

    monkeypatch.setattr(cli, "Settings", factory)
    return created


@pytest.fixture
def cli_agent(monkeypatch: pytest.MonkeyPatch, cli_settings: list[Settings]) -> CLIAnswerAgent:
    agent = CLIAnswerAgent()
    monkeypatch.setitem(
        sys.modules, "rag_agent.graph", SimpleNamespace(Agent=lambda settings: agent)
    )
    return agent


def test_help_lists_delivered_commands() -> None:
    result = runner.invoke(cli.app, ["--help"])
    assert result.exit_code == 0
    for command in [
        "ingest",
        "ask",
        "chat",
        "stats",
        "doctor",
        "eval",
        "cost-report",
        "bench",
        "diagram",
        "smoke",
    ]:
        assert command in result.stdout


def test_doctor_reports_safe_configuration_without_loading_agent(
    monkeypatch: pytest.MonkeyPatch, cli_settings: list[Settings]
) -> None:
    monkeypatch.setattr(cli.importlib.util, "find_spec", lambda module: object())
    result = runner.invoke(cli.app, ["doctor"])
    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert report["provider"] == "local"
    assert report["api_auth_enabled"] is False
    assert report["data_dir"] == str(cli_settings[0].data_dir.resolve())
    assert all(report["dependencies"].values())
    assert "openai_api_key" not in report


def test_doctor_identifies_missing_dependency(
    monkeypatch: pytest.MonkeyPatch, cli_settings: list[Settings]
) -> None:
    monkeypatch.setattr(
        cli.importlib.util, "find_spec", lambda module: None if module == "chromadb" else object()
    )
    result = runner.invoke(cli.app, ["doctor"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["dependencies"]["chromadb"] is False


def test_ask_json_preserves_typed_sources_usage_and_question(cli_agent: CLIAnswerAgent) -> None:
    result = runner.invoke(cli.app, ["ask", "How do functions work?", "--json"])
    assert result.exit_code == 0
    response = json.loads(result.stdout)
    assert response["answerable"] is True
    assert response["sources"][0]["url"] == SOURCE
    assert response["sources"][0]["evidence"] == EVIDENCE
    assert response["usage"]["input_tokens"] == 5
    assert response["usage"]["estimated_usd"] == 0.000001
    assert response["request_id"] == "cli-test-request"
    assert cli_agent.calls == [("How do functions work?", True)]


@pytest.mark.parametrize("context", [False, True])
def test_ask_text_source_links_and_optional_context(
    cli_agent: CLIAnswerAgent, context: bool
) -> None:
    arguments = ["ask", "How do functions work?"] + (["--show-context"] if context else [])
    result = runner.invoke(cli.app, arguments)
    assert result.exit_code == 0
    assert "Functions introduce reusable behavior." in result.stdout
    assert "Python functions" in result.stdout and SOURCE in result.stdout
    assert (EVIDENCE in result.stdout) == context
    assert "Estimated new cost: $0.000001; cached: false" in result.stdout


def test_stats_returns_agent_snapshot(cli_agent: CLIAnswerAgent) -> None:
    result = runner.invoke(cli.app, ["stats"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == cli_agent.stats()
    assert not cli_agent.calls


def test_chat_answers_and_quits_without_querying_exit_command(cli_agent: CLIAnswerAgent) -> None:
    result = runner.invoke(cli.app, ["chat"], input="How do functions work?\n/quit\n")
    assert result.exit_code == 0
    assert "Functions introduce reusable behavior." in result.stdout
    assert cli_agent.calls == [("How do functions work?", True)]


def test_chat_handles_whitespace_and_eof(cli_agent: CLIAnswerAgent) -> None:
    result = runner.invoke(cli.app, ["chat"], input="   \n")
    assert result.exit_code == 0
    assert not cli_agent.calls


@pytest.mark.parametrize(
    "exception,code,expected",
    [
        (FileNotFoundError("private-index-path"), 2, "No index found"),
        (RuntimeError("secret-provider-key"), 1, "Cannot load the index (RuntimeError)"),
    ],
)
def test_agent_loading_errors_have_safe_cli_messages(
    monkeypatch: pytest.MonkeyPatch,
    cli_settings: list[Settings],
    exception: Exception,
    code: int,
    expected: str,
) -> None:
    def broken(settings: Settings) -> None:
        raise exception

    monkeypatch.setitem(sys.modules, "rag_agent.graph", SimpleNamespace(Agent=broken))
    result = runner.invoke(cli.app, ["ask", "Python?"])
    assert result.exit_code == code
    assert expected in result.stderr
    assert "private-index-path" not in result.output
    assert "secret-provider-key" not in result.output


def test_query_error_is_safe(monkeypatch: pytest.MonkeyPatch, cli_agent: CLIAnswerAgent) -> None:
    def broken(question: str, use_cache: bool = True) -> Answer:
        raise RuntimeError("secret-provider-body")

    monkeypatch.setattr(cli_agent, "ask", broken)
    result = runner.invoke(cli.app, ["ask", "Python?"])
    assert result.exit_code == 1
    assert "The query could not be completed (RuntimeError)" in result.stderr
    assert "secret-provider-body" not in result.output


@pytest.mark.parametrize("command", [["doctor"], ["ingest"]])
def test_configuration_errors_do_not_expose_values(
    monkeypatch: pytest.MonkeyPatch, command: list[str]
) -> None:
    def invalid(**overrides: Any) -> Settings:
        raise ValueError("secret-setting-value")

    monkeypatch.setattr(cli, "Settings", invalid)
    monkeypatch.setitem(
        sys.modules, "rag_agent.ingest", SimpleNamespace(ingest=lambda *args, **kwargs: None)
    )
    result = runner.invoke(cli.app, command)
    assert result.exit_code == 2
    assert "Invalid configuration" in result.stderr
    assert "secret-setting-value" not in result.output
    assert "Ingestion failed" not in result.output


def test_ingest_forwards_validated_options_to_async_pipeline(
    monkeypatch: pytest.MonkeyPatch, cli_settings: list[Settings]
) -> None:
    calls: list[tuple[Settings, bool, bool]] = []

    async def ingest(
        settings: Settings, force: bool = False, dry_run: bool = False
    ) -> dict[str, Any]:
        calls.append((settings, force, dry_run))
        return {"pages": 4, "chunks": 22, "dry_run": dry_run}

    monkeypatch.setitem(sys.modules, "rag_agent.ingest", SimpleNamespace(ingest=ingest))
    result = runner.invoke(
        cli.app, ["ingest", "--start-url", SOURCE, "--max-pages", "7", "--force", "--dry-run"]
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"pages": 4, "chunks": 22, "dry_run": True}
    assert len(calls) == 1
    configuration, force, dry_run = calls[0]
    assert configuration.start_url == SOURCE and configuration.max_pages == 7
    assert force and dry_run


def test_ingest_failure_reports_type_without_secret(
    monkeypatch: pytest.MonkeyPatch, cli_settings: list[Settings]
) -> None:
    async def broken(
        settings: Settings, force: bool = False, dry_run: bool = False
    ) -> dict[str, Any]:
        raise OSError("private-path-or-provider-credential")

    monkeypatch.setitem(sys.modules, "rag_agent.ingest", SimpleNamespace(ingest=broken))
    result = runner.invoke(cli.app, ["ingest"])
    assert result.exit_code == 1
    assert "Ingestion failed (OSError)" in result.stderr
    assert "private-path-or-provider-credential" not in result.output


def test_invalid_page_limit_is_rejected_before_pipeline_runs(
    monkeypatch: pytest.MonkeyPatch, cli_settings: list[Settings]
) -> None:
    calls: list[Any] = []
    monkeypatch.setitem(
        sys.modules,
        "rag_agent.ingest",
        SimpleNamespace(ingest=lambda *args, **kwargs: calls.append(args)),
    )
    result = runner.invoke(cli.app, ["ingest", "--max-pages", "0"])
    assert result.exit_code == 2
    assert not calls


def test_eval_passes_existing_benchmark_and_output_directory(
    monkeypatch: pytest.MonkeyPatch, cli_settings: list[Settings], tmp_path: Path
) -> None:
    benchmark = tmp_path / "questions.json"
    benchmark.write_text('{"questions": []}', encoding="utf-8")
    output = tmp_path / "reports"
    calls: list[tuple[Settings, Path, Path]] = []

    def evaluate(settings: Settings, questions: Path, out: Path) -> dict[str, Any]:
        calls.append((settings, questions, out))
        return {"run_id": "test-run", "count": 2}

    monkeypatch.setitem(
        sys.modules, "evaluation.run_eval", SimpleNamespace(run_evaluation=evaluate)
    )
    result = runner.invoke(cli.app, ["eval", "--questions", str(benchmark), "--out", str(output)])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"run_id": "test-run", "count": 2}
    assert calls == [(cli_settings[0], benchmark, output)]


def test_eval_requires_an_existing_question_file(tmp_path: Path) -> None:
    result = runner.invoke(cli.app, ["eval", "--questions", str(tmp_path / "missing.json")])
    assert result.exit_code == 2


def test_cost_report_loads_measured_json_and_emits_written_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = tmp_path / "results.json"
    measured = {"provider": "local", "questions": [{"usage": {"estimated_usd": 0}}]}
    source.write_text(json.dumps(measured), encoding="utf-8")
    destination = tmp_path / "COST_ANALYSIS.md"
    calls: list[tuple[dict[str, Any], Path]] = []

    def report(data: dict[str, Any], out: Path) -> str:
        calls.append((data, out))
        out.write_text("# Measured local cost", encoding="utf-8")
        return "# Measured local cost"

    monkeypatch.setitem(
        sys.modules, "evaluation.reporting", SimpleNamespace(generate_cost_report=report)
    )
    result = runner.invoke(
        cli.app, ["cost-report", "--report", str(source), "--out", str(destination)]
    )
    assert result.exit_code == 0
    assert calls == [(measured, destination)]
    assert destination.read_text(encoding="utf-8") == "# Measured local cost"
    assert str(destination.resolve()) in result.stdout


def test_diagram_exports_graph_boundary_to_requested_file(
    cli_agent: CLIAnswerAgent, tmp_path: Path
) -> None:
    destination = tmp_path / "nested" / "graph.mmd"
    result = runner.invoke(cli.app, ["diagram", "--out", str(destination)])
    assert result.exit_code == 0
    assert destination.read_text(encoding="utf-8") == "graph TD; retrieve-->verify;"
    assert str(destination.resolve()) in result.stdout
    assert not cli_agent.calls


def test_bench_disables_cache_and_aggregates_observed_usage_and_stages(
    cli_agent: CLIAnswerAgent, tmp_path: Path
) -> None:
    destination = tmp_path / "nested" / "benchmark.json"
    result = runner.invoke(cli.app, ["bench", "--runs", "3", "--out", str(destination)])
    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert json.loads(destination.read_text(encoding="utf-8")) == report
    assert report["runs"] == 3 and report["unique_questions"] == 3
    assert report["cache_enabled"] is False
    assert len(cli_agent.calls) == 3 and all(not cached for _, cached in cli_agent.calls)
    assert report["estimated_usd"] == pytest.approx(0.000003)
    assert report["stages"]["retrieval"]["mean_ms"] == 1.0
    assert report["stages"]["generation"]["p95_ms"] == 2.0
    assert report["total"]["mean_ms"] >= 0
    assert report["total"]["p95_ms"] >= report["total"]["p50_ms"]


def test_bench_rejects_zero_runs(cli_agent: CLIAnswerAgent, tmp_path: Path) -> None:
    destination = tmp_path / "benchmark.json"
    result = runner.invoke(cli.app, ["bench", "--runs", "0", "--out", str(destination)])
    assert result.exit_code == 2
    assert not cli_agent.calls and not destination.exists()


def test_smoke_checks_grounded_answers_and_refusal_with_cache_disabled(
    cli_agent: CLIAnswerAgent,
) -> None:
    result = runner.invoke(cli.app, ["smoke"])
    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert report["passed"] is True
    assert len(report["results"]) == 5
    assert [item["answerable"] for item in report["results"]] == [True, True, True, True, False]
    assert all(item["passed"] for item in report["results"])
    assert len(cli_agent.calls) == 5 and all(not cached for _, cached in cli_agent.calls)


def test_smoke_fails_answerable_response_without_evidence(
    monkeypatch: pytest.MonkeyPatch, cli_agent: CLIAnswerAgent
) -> None:
    monkeypatch.setattr(
        cli_agent,
        "ask",
        lambda question, use_cache=True: Answer(answer="unsupported", answerable=True),
    )
    result = runner.invoke(cli.app, ["smoke"])
    assert result.exit_code == 1
    report = json.loads(result.stdout)
    assert report["passed"] is False
    assert not any(item["passed"] for item in report["results"])
