# FALCON MVP Skeleton Design

## Summary

Build the first CLI-only FALCON MVP as a lightweight layered Python project using `src/` layout, `uv`, Typer, and PyYAML. The MVP implements real configuration loading, path/schema inspection, and an occurrence-level `context` query prototype. It does not implement homology search, co-localization statistics, candidate screening, agent reasoning, dynamic tool generation, or InterProScan execution.

## Key Decisions

- Config precedence is `CLI > YAML > defaults`.
- Default context window is upstream/downstream N CDS.
- `falcon context` also supports a base-pair span mode.
- Context output is JSON to stdout.
- Routine tests use tiny temporary SQLite/CSV fixtures.
- Documentation is English-first.

## Cluster Semantics

Future statistics should use clusters for redundancy and aggregation, while evidence stays at occurrence level:

- Homology search can use 90% or 30% MMseqs databases.
- If 30% search is used, all corresponding 90% members' occurrence contexts should be extracted for statistics.
- If 90% search is used, an optional parameter may expand to other members in the same 30% cluster.
- Co-localization statistics should merge neighbor proteins to 30% clusters.

## MVP Commands

- `falcon config show`: print effective configuration.
- `falcon inspect`: inspect configured databases, manifests, and tool paths without heavy scans.
- `falcon context PROTEIN_ID`: extract occurrence-level context for a real protein ID.

## Testing

Tests should cover config precedence, manifest parsing, fixture SQLite context extraction, and CLI JSON outputs.
