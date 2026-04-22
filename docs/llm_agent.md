# LLM Agent Runtime

FALCON now exposes one LLM-backed reasoning runtime. It does not support the historical deterministic / single / team workflow split.

## Runtime shape

For each candidate neighbor protein, FALCON:

1. builds deterministic evidence inputs
2. initializes a `ResearchNotebook`
3. asks the `ProgramPlanner` for a short agenda
4. executes one program step through allowlisted tools
5. updates the notebook and audit ledger
6. optionally escalates to a lightweight cohort investigator
7. asks the synthesizer for a conservative supported claim and next-step recommendations

## Configuration

Relevant YAML keys:

```yaml
agent:
  query_catalog: runs/example-search/seeds.jsonl
  program_planner:
    max_rounds: 2
    prompt_dir: prompts/agent/reasoning
    schema_retries: 2
  tools:
    manifest: configs/tool_manifest.yaml
    max_expensive_tools_per_candidate:
    interproscan:
      policy: on_demand
    mmseqs:
      max_hits: 25
  literature:
    sources: [europe_pmc, pubmed]
    max_results_per_source: 5
  llm:
    mode: live
    model_name:
    base_url:
    api_key_env: OPENAI_API_KEY
    temperature: 0.2
    max_tokens: 2000
    replay_path:
  reporting:
    ledger_dir: ledgers
```

`agent.query_catalog` is required. FALCON no longer infers seed metadata from an upstream run directory.

`agent.llm.mode` may be:

- `mock`
- `live`
- `replay`

`deterministic` mode was removed. Live mode still requires an explicit `model_name`.

## Prompts

Prompts live under `prompts/agent/reasoning/`.

Current prompt files:

- `program_planner.yaml`
- `synthesizer.yaml`

There is no longer a prompt-pack action loop.

## Audit artifacts

The runtime writes:

- `program_trace.jsonl`
- `tool_results.jsonl`
- `agent_events.jsonl`
- `ledgers/*.json`
- `reports/*.md`

The evidence graph inside each ledger is an audit substrate for executed facts. It is not the reasoning backbone.
