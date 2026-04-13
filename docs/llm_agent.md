# LLM Agent Loop

FALCON's LLM agent mode evaluates one candidate neighbor protein at a time. It does not run broad autonomous tools. The loop only exposes read-only evidence already collected by the pipeline:

- co-localization statistics for the candidate neighbor cluster,
- occurrence-level genomic context examples,
- SQLite annotations and cluster mappings,
- protein and DNA sequence availability summaries.

## Configuration

LLM settings live under `agent.llm` in YAML and can be overridden from the CLI.

```yaml
agent:
  llm:
    mode: deterministic
    provider: openai
    model_name:
    base_url:
    api_key_env: OPENAI_API_KEY
    temperature: 0.2
    max_tokens: 2000
    prompt_pack: prompts/agent/falsification_loop.yaml
    max_iterations: 6
    replay_path:
```

`mode` can be:

- `deterministic`: rule-based MVP reasoning, no LLM calls.
- `mock`: scripted provider for tests and local trace checks.
- `live`: OpenAI-compatible Chat Completions through the OpenAI Python SDK.
- `replay`: replays responses from a previous `llm_calls.jsonl`.

Live mode requires `model_name`; FALCON does not provide a guessed model default. Custom endpoints use `base_url`.

## Prompt Packs

Prompt packs are YAML files under `prompts/agent/`. A prompt pack must define:

- `name`
- `version`
- `system`
- `developer_guidance`
- `action_schema.allowed_actions`
- `tool_policy`
- `output_contract`

The default pack is `prompts/agent/falsification_loop.yaml`.

## Artifacts

LLM runs write:

- `agent_results.jsonl`: final per-candidate evidence and verdicts.
- `agent_trace.jsonl`: action and observation trace for each loop iteration.
- `llm_calls.jsonl`: replayable model requests and responses.
- `reports/*.md`: human-readable candidate reports.
