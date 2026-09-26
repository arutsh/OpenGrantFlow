# Tasks

Workflow rule: one task group = one GitHub sub-issue (of this change's parent issue) = one PR, merged before the next group starts.

## 1. Adversarial suite and evidence gathering

- [ ] 1.0 Run `scripts/flow.py start chat-fix-prompt-injection-provenance 1` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 1.1 Add a mocked-`AiClient` adversarial test module in `services/chat/tests` covering: a tool not offered for the page, a model-supplied `budget_id`/`customer_id`, parameter substitution from a poisoned description, and a creating tool with injected values. Assert on the actual registry dispatch (tool, params, target id, token); verify every guard scenario in `specs/chat-conversations/spec.md` passes or is fixed.
- [ ] 1.2 Add an end-to-end chat test showing the current flow: a poisoned description, `get_budget_summary`, then a follow-up turn. Capture the history sent to `decide`; it should show the injected text arriving as an assistant turn (documenting the baseline).
- [ ] 1.3 Write `scripts/eval_prompt_injection.py` (opt-in, not CI) that replays the poisoned conversation against configured providers and reports the tool-call rate; ask the user to run it and paste the results into the PR description.
- [ ] 1.4 Run `pytest services/chat` and `flake8 --max-line-length=100` clean; PR merged.

## 2. Provenance-preserving storage and replay — ticket depends on 1

- [ ] 2.0 Run `scripts/flow.py start chat-fix-prompt-injection-provenance 2` to move this group to In Progress and create its branch before starting any other work in this group.
- [ ] 2.1 Add an `external_data` role to `ChatTurn` and map it in `decide_service._history_to_model_messages` to a delimited `UserPromptPart` with escaping; verify with unit tests that no `ModelResponse` part contains external data and that delimiter injection is escaped.
- [ ] 2.2 Change the orchestrator and `save_turn` so tool turns store a fixed application-authored `content` and keep raw output only in `tool_result`, and change `to_chat_turns` to emit `external_data` turns from `tool_name`/`tool_result` (description-free summary form), including for old rows; verify with the 1.2 test, now asserting that no description text is replayed.
- [ ] 2.3 Remove the "from the message or conversation history" parameter-sourcing wording from `SYSTEM_PROMPT` and bump the prompt version used in audit logs; verify the existing decide tests pass.
- [ ] 2.4 Confirm the chat UI still shows the full tool output via `action_result` (frontend test or manual check on local dev); run `pytest services/chat services/ai` and `flake8 --max-line-length=100` clean; PR merged.
