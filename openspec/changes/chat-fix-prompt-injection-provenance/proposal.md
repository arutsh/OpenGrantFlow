## Why

We traced an indirect prompt-injection path in the chat agent. **The data flow is confirmed; that a model can actually be exploited through it is not.**

1. Budget line descriptions and budget names are untrusted. They are written by any member of the company, and often extracted by AI from a donor's Excel file.
2. `get_budget_summary` in `budget_tool_registry.py` embeds the name and up to five raw descriptions in `ToolResult.message`.
3. The orchestrator returns that message as `TurnResult.reply`. `save_turn` stores it as an ordinary `role="assistant"` message.
4. On every later turn, `to_chat_turns` replays it, and `decide_service._history_to_model_messages` turns it into a `ModelResponse` `TextPart`. The model sees the untrusted text **as its own earlier words**, next to a tool list that includes write tools (`add_budget_line`, `update_budget`, `create_budget*`).
5. The system prompt tells the model to take tool parameters "from the message or conversation history", which invites it to pull parameters from the replayed data.

Guards already in code: one tool per turn; pydantic validation of parameters; `budget_id` injected from the client's `context_id` and never chosen by the model (see the `chat-tool-registry` spec); calls run with the user's own token. The worst plausible outcome is therefore an unrequested write to the user's *currently open* budget, or a new budget, after the user sends some unrelated follow-up message. It cannot cross tenants.

## What Changes

- **Investigate and measure:** an adversarial test suite that runs the orchestrator against a scripted (mocked) model. It checks that code-level guards hold whatever the model decides, including unauthorized tool selection, parameter substitution and resource targeting. It also adds an opt-in live-model evaluation that records whether real providers follow injected instructions. No exploitability claim goes into docs or issues without output from that run.
- **Preserve provenance:** tool output is persisted separately from assistant prose. The assistant reply for a tool turn is a fixed, application-authored sentence. Tool-derived external data is replayed to the model only as explicitly marked external data in the request-side role, never as the model's own words.
- **Stop replaying raw untrusted fields where they aren't needed:** the summary tool's replayable form drops descriptions (counts and totals only). The user-facing UI still shows the full preview.
- The system prompt stops telling the model to source parameters from history. This is a supporting fix, not the defense.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `chat-conversations`: stored messages distinguish application-authored replies from external tool data, and replay keeps that distinction.
- `ai-decide`: conversation history accepts a data-only turn type that is never presented to the model as assistant output.

## Impact

- `services/chat/app/services/orchestrator.py`, `budget_tool_registry.py`, `app/crud/conversation.py`, `app/models` (message provenance column plus a migration)
- `shared/ai_client/schemas.py` (`ChatTurn` role gains an external-data variant, or a separate field)
- `services/ai/app/services/decide_service.py` (history mapping, system prompt)
- New test suites in chat (mocked model) and an opt-in eval script
