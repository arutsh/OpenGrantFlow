"""Opt-in live site-assistant eval, not run in CI: probes the configured provider per category.
Run from services/ai: AI_TEST_POSTGRES_URL=... python scripts/eval_site_assistant.py --runs 3"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

from app.core.config import settings  # noqa: E402
from app.services import site_assistant  # noqa: E402
from app.services.provider import ResolvedModel, resolve_site_assistant_model  # noqa: E402
from tests.evals.site_assistant_eval import (  # noqa: E402
    CATEGORIES,
    Probe,
    ProbeResult,
    answer_violations,
    eval_corpus_session,
    format_report,
    load_probes,
    model_violations,
    seeded_prompt,
)


async def _run_probe(db, probe: Probe, resolved: ResolvedModel, verbose: bool) -> ProbeResult:
    """Ask once, scoring the raw model output and the served response separately."""
    seen: dict = {}
    real_retrieve = site_assistant.retrieve
    real_resolve = site_assistant.resolve_citations

    async def _retrieve(*args, **kwargs):
        seen["chunks"] = await real_retrieve(*args, **kwargs)
        return seen["chunks"]

    def _resolve(output, chunks):
        seen["output"] = output
        return real_resolve(output, chunks)

    with (
        patch.object(site_assistant, "retrieve", _retrieve),
        patch.object(site_assistant, "resolve_citations", _resolve),
    ):
        response = await site_assistant.ask(db, probe.question, probe.persona, resolved)

    chunks = seen["chunks"]
    if not chunks or chunks[0].score < settings.SITE_ASSISTANT_MIN_SCORE:
        return ProbeResult(probe, short_circuited=True)
    output = seen.get("output")
    if output is None:
        return ProbeResult(probe, short_circuited=False, model_error=True)

    retrieved = {c.content_id for c in chunks}
    result = ProbeResult(
        probe,
        short_circuited=False,
        model_violations=model_violations(output.answer, output.cited_chunk_ids, retrieved, probe),
        served_violations=answer_violations(response.answer, probe),
    )
    if verbose:
        print(f"[{probe.id}] answerable={output.answerable} cited={output.cited_chunk_ids}")
        print(f"  raw: {output.answer}")
        print(f"  violations: {result.model_violations or 'none'}")
    return result


async def main(runs: int, category: str | None, verbose: bool) -> int:
    resolved = resolve_site_assistant_model()
    if resolved is None:
        print("No model resolved: check SITE_ASSISTANT_PROVIDER and its key or Ollama origin.")
        return 1
    probes = [p for p in load_probes() if category in (None, p.category)]
    prompt = seeded_prompt()
    print(
        f"provider={resolved.provider_name} model={resolved.model_name} "
        f"prompt={prompt.name} {prompt.version} probes={len(probes)} runs={runs}\n"
    )

    results: list[ProbeResult] = []
    with patch.object(site_assistant, "load_prompt", AsyncMock(return_value=prompt)):
        async with eval_corpus_session("eval_site_assistant_live") as db:
            for probe in probes:
                for _ in range(runs):
                    results.append(await _run_probe(db, probe, resolved, verbose))

    print(format_report(results))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", type=int, default=3, help="repeats per probe")
    parser.add_argument("--category", choices=CATEGORIES, help="only run one category")
    parser.add_argument("--verbose", action="store_true", help="print each raw model answer")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    sys.exit(asyncio.run(main(args.runs, args.category, args.verbose)))
