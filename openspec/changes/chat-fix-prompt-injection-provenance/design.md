# Design

## Context

See proposal.md for the traced data flow. Additional facts:

- `Message` already has `tool_name`, `tool_params` and `tool_result` columns. `tool_result.message` duplicates `content` for tool turns. So provenance storage mostly exists already. The bug is that `content` is set to the tool's raw output.
- `to_chat_turns` already skips non-user/assistant rows. `ChatTurn.role` is `Literal["user", "assistant"]`.
- `chat-tool-registry` already requires `budget_id` to be injected from `context_id`. The orchestrator does this for `targeted_tools`, but it builds `params` from `validated.model_dump()`, so an extra `budget_id` from the model is dropped only if the param model doesn't declare it. The adversarial suite pins this down.

## Goals / Non-Goals

**Goals:** evidence-based assessment; untrusted text is never replayed with assistant authority; tests that pin the code-level guards.

**Non-Goals:**
- Relying on prompt wording as the defense.
- A human-confirmation gate for every write tool. This is the strongest structural control, but it changes the chat UX. Decide it after group 1's live evaluation, as a follow-up change if the evaluation shows real models acting on injected data.
- Injection through other untrusted inputs to AI extraction, such as the Excel import prompt. The extraction output is itself validated and reviewed as a draft. Note it in the group 1 report for a separate look.

## Decisions

1. **Mocked-model adversarial suite first.** A fake `AiClient.decide` returns scripted `ToolCall`s: a tool outside the page's toolset, extra `budget_id`/`customer_id` params, parameter values copied from a poisoned description, and a creating tool with injected names. It asserts on what the registry actually dispatches. This proves the code guards without any model.
2. **Opt-in live evaluation** (`scripts/eval_prompt_injection.py`, not run in CI) replays a poisoned conversation against configured providers N times and records the tool-call rate. The results go into the group 1 PR description as the evidence base.
3. **Provenance representation:** add `"external_data"` to the `ChatTurn` role literal instead of a separate flag, so that exhaustive handling in `_history_to_model_messages` fails loudly on an unhandled role. The AI service maps it to a `UserPromptPart` wrapped in a fixed delimiter (`<external_data source="tool:get_budget_summary">…</external_data>`), with delimiter characters escaped in the content.
4. **Assistant content for tool turns** becomes a fixed per-tool template, e.g. "Here's the budget summary." The SSE `action_result` event still streams the full tool output to the UI, so users lose nothing visible. The replayed external-data form omits free-text descriptions: summaries replay only the name, line count and total.
5. **No migration of old rows' content.** Old assistant rows that contain raw summaries remain. The replay path re-derives the content from `tool_name`/`tool_result` when those are present, so old rows are also replayed safely.

## Risks / Trade-offs

- [Model loses useful context once descriptions are not replayed] → the user can ask again, and the tool runs fresh. This is an accepted trade for safety.
- [Delimiter escaping mistakes] → unit-test the escaping with delimiter-containing payloads.
- [Live eval costs money or rate limits] → opt-in, small N, run by the user.
