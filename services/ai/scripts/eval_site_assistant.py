"""Opt-in paid answer eval, not run in CI: one configuration over the golden set and probes.
Run from services/ai: AI_TEST_POSTGRES_URL=... python scripts/eval_site_assistant.py run"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

from app.core.config import settings  # noqa: E402
from app.services.provider import (  # noqa: E402
    ResolvedModel,
    _platform_anthropic_model,
    build_ollama_model,
    resolve_site_assistant_model,
)
from tests.evals.answer_eval import (  # noqa: E402
    BaselineRefused,
    EstimateOverCap,
    EvalConfigError,
    UnpricedModel,
    evaluate_gate,
    format_answer_report,
    format_comparison,
    format_gate_report,
    load_baseline,
    load_config,
    load_judge_prompt,
    run_answer_eval,
    run_comparison,
    write_baseline,
    write_result,
)
from tests.evals.site_assistant_eval import eval_corpus_session, seeded_prompt  # noqa: E402


def _setup():
    """Config, judge prompt, production model and judge, or an error message."""
    try:
        config = load_config()
        judge_prompt = load_judge_prompt(config.judge_prompt_version)
    except EvalConfigError as exc:
        return f"Refusing to run: {exc}"
    resolved = resolve_site_assistant_model()
    if resolved is None:
        return "No model resolved: check SITE_ASSISTANT_PROVIDER and its key or Ollama origin."
    judge = _platform_anthropic_model(config.judge_model)
    if judge is None:
        return "No judge model: the judge runs on the platform ANTHROPIC_API_KEY, which is unset."
    return config, judge_prompt, resolved, judge


def _candidate_model(production: ResolvedModel, name: str) -> ResolvedModel | None:
    if production.provider_name == "anthropic":
        return _platform_anthropic_model(name)
    return build_ollama_model(settings.OLLAMA_URL, name, "site-assistant")


async def run(result_path: Path | None, gate: bool, write: bool) -> int:
    setup = _setup()
    if isinstance(setup, str):
        print(setup)
        return 1
    config, judge_prompt, resolved, judge = setup
    try:
        async with eval_corpus_session("eval_answer_live") as db:
            result = await run_answer_eval(
                db, resolved, seeded_prompt(), config, judge, judge_prompt
            )
    except (UnpricedModel, EstimateOverCap) as exc:
        print(f"Refusing to run: {exc}")
        return 1

    print(format_answer_report(result))
    if result_path is not None:
        write_result(result, result_path)
    if gate:
        try:
            report = evaluate_gate(result, load_baseline(), config)
        except EvalConfigError as exc:
            print(exc)
            return 1
        print("\n" + format_gate_report(report))
        return 0 if report.passed else 1
    if write:
        try:
            write_baseline(result)
        except BaselineRefused as exc:
            print(f"Baseline not written: {exc}")
            return 1
        print("Baseline written.")
    return 0 if result.complete else 1


async def compare(candidate_model: str | None, candidate_prompt: str | None) -> int:
    setup = _setup()
    if isinstance(setup, str):
        print(setup)
        return 1
    config, judge_prompt, resolved, judge = setup
    try:
        prompt_version = load_baseline()["configuration"]["prompt_version"]
        production = (resolved, seeded_prompt(prompt_version))
        candidate_resolved = resolved
        if candidate_model:
            candidate_resolved = _candidate_model(resolved, candidate_model)
            if candidate_resolved is None:
                print("Candidate model could not be built: is the provider key set?")
                return 1
        candidate = (candidate_resolved, seeded_prompt(candidate_prompt or prompt_version))
        async with eval_corpus_session("eval_answer_compare") as db:
            results = await run_comparison(db, production, candidate, config, judge, judge_prompt)
    except (EvalConfigError, ValueError, EstimateOverCap) as exc:
        print(f"Refusing to run: {exc}")
        return 1
    print(format_comparison(*results))
    return 0 if all(r.complete for r in results) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run", help="evaluate the configured production setup")
    run_parser.add_argument("--result", type=Path, help="write the machine-readable result here")
    mode = run_parser.add_mutually_exclusive_group()
    mode.add_argument("--gate", action="store_true", help="fail if worse than the baseline")
    mode.add_argument("--write-baseline", action="store_true", help="record a complete run")
    cmp_parser = commands.add_parser("compare", help="production vs a candidate configuration")
    cmp_parser.add_argument("--candidate-model")
    cmp_parser.add_argument("--candidate-prompt")
    args = parser.parse_args()
    if args.command == "compare":
        if not (args.candidate_model or args.candidate_prompt):
            parser.error("compare needs --candidate-model and/or --candidate-prompt")
        sys.exit(asyncio.run(compare(args.candidate_model, args.candidate_prompt)))
    sys.exit(asyncio.run(run(args.result, args.gate, args.write_baseline)))
