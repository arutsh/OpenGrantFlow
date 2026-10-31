"""Opt-in paid answer eval, not run in CI: one configuration over the golden set and probes.
Run from services/ai: AI_TEST_POSTGRES_URL=... python scripts/eval_site_assistant.py run"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

from app.services.provider import resolve_site_assistant_model  # noqa: E402
from tests.evals.answer_eval import (  # noqa: E402
    EstimateOverCap,
    UnpricedModel,
    format_answer_report,
    load_config,
    run_answer_eval,
    write_result,
)
from tests.evals.site_assistant_eval import eval_corpus_session, seeded_prompt  # noqa: E402


async def run(result_path: Path | None) -> int:
    config = load_config()
    resolved = resolve_site_assistant_model()
    if resolved is None:
        print("No model resolved: check SITE_ASSISTANT_PROVIDER and its key or Ollama origin.")
        return 1
    try:
        async with eval_corpus_session("eval_answer_live") as db:
            result = await run_answer_eval(db, resolved, seeded_prompt(), config)
    except (UnpricedModel, EstimateOverCap) as exc:
        print(f"Refusing to run: {exc}")
        return 1

    print(format_answer_report(result))
    if result_path is not None:
        write_result(result, result_path)
    return 0 if result.complete else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run", help="evaluate the configured production setup")
    run_parser.add_argument("--result", type=Path, help="write the machine-readable result here")
    args = parser.parse_args()
    sys.exit(asyncio.run(run(args.result)))
