# FALCON: A Falsification-First Agentic System for Metagenomic Discovery

## 1. Project Vision

FALCON is an agentic system designed to discover **previously unknown functional genetic systems** from microbial metagenomic assemblies or genomes.

Unlike traditional pipelines, FALCON treats discovery as a **structured, auditable scientific reasoning process**, not as pattern matching or classification.

The system continuously:
- generates biological hypotheses
- attempts to falsify them
- revises its beliefs based on contradictions
- produces traceable, reproducible conclusions

The goal is not only to find new systems, but to ensure that **every accepted claim has survived systematic attempts to disprove it**.

---

## 2. Core Design Principles

### 2.1 Falsification First
Every hypothesis must include:
- supporting evidence
- explicit falsification conditions

The system prioritizes:
> “What observation would prove this wrong?”

over:
> “What supports this idea?”

---

### 2.2 Traceable Scientific Reasoning
All outputs must be:
- reproducible
- auditable
- linked to raw observations and tools

No conclusion is allowed without:
- data provenance
- tool execution trace
- reasoning path

---

### 2.3 Controlled Adaptivity
FALCON can extend its analytical capabilities, but only under strict governance:
- Prefer existing tools
- Generate new tools only when an evidence gap is detected
- Validate before reuse

---

### 2.4 Separation of Concerns
The system separates:
- **signal extraction (deterministic tools)**
- **hypothesis reasoning (LLM)**
- **validation (tool execution)**
- **memory (evidence graph)**

---

## 3. Problem Context

Current approaches fail in three key ways:

### Rule-based pipelines
- High precision
- Low novelty detection
- Cannot generalize beyond predefined patterns

### LLM-only agents
- Flexible but unreliable
- Prone to confirmation bias
- Weak traceability

### Static tool ecosystems
- Cannot handle long-tail biological questions
- Require manual scripting for edge cases

---

## 4. System Overview

FALCON is structured as a closed-loop reasoning system with specialized roles.

### 4.1 Candidate Builder
Transforms raw genomic data into structured neighborhoods:
- extract genomic regions
- normalize coordinates
- prepare analysis-ready objects

---

### 4.2 Feature Extraction Layer
Aggregates deterministic signals:
- homology hits
- domain annotations
- compositional features
- mobile element signals

Output is a unified feature bundle.

---

### 4.3 Hypothesis Generator
Produces candidate biological explanations:
- system type hypotheses
- functional roles
- evolutionary scenarios

Each hypothesis must include:
- expected observations
- falsification conditions
- alternative explanations

---

### 4.4 Deduction Planner
Transforms hypotheses into testable plans:
- identifies required observations
- maps to tools or analysis strategies
- prioritizes high-impact falsification tests

---

### 4.5 Tool Broker
Responsible for executing or creating tools:

Three levels:
1. Existing tools (preferred)
2. Heavy adapters (pre-integrated pipelines)
3. Generated tools (only when necessary)

---

### 4.6 Falsifier / Auditor
Challenges current hypotheses:
- searches for contradictions
- tests alternative explanations
- flags weak assumptions

---

### 4.7 Evidence System
Maintains structured memory of:
- entities (genes, proteins, motifs, regions)
- relationships (co-localization, homology, support, contradiction)
- observations
- tool outputs

---

### 4.8 Contradiction Ledger
Records failed hypotheses explicitly:
- what was proposed
- what disproved it
- what replaced it

This prevents repeated reasoning errors.

---

### 4.9 Synthesizer
Produces final outputs:
- best-supported hypothesis
- rejected alternatives
- evidence summary
- uncertainty assessment

---

## 5. Discovery Loop

FALCON operates in an iterative loop:

1. Perceive → build candidate
2. Hypothesize → propose explanations
3. Deduce → derive tests
4. Select/Create Tool → obtain evidence
5. Observe → record results
6. Audit → search contradictions
7. Revise → update beliefs
8. Stop → when sufficient or blocked

---

## 6. Output Requirements

Every result must include:

- Final hypothesis
- Competing hypotheses considered
- Supporting evidence
- Falsification attempts performed
- Remaining uncertainties
- Tool execution trace

---

## 7. Failure Modes (Explicitly Handled)

The system must explicitly detect and handle:

- Insufficient evidence
- Conflicting signals
- Fragmented assemblies
- Tool failures
- Unresolvable ambiguity

The correct behavior is:
> return uncertainty, not hallucinated explanation

---

## 8. Dynamic Tooling Philosophy

Tool generation is allowed but constrained:

### Allowed when:
- No existing method can test a critical falsifier
- The problem is local and well-defined

### Required validation:
- deterministic output
- test case pass
- schema compliance

### Promotion:
- frequently reused tools become persistent skills

---

## 9. Development Priorities

The system should be built in stages:

### Stage 1
- deterministic feature extraction
- candidate representation
- basic reporting

### Stage 2
- hypothesis + falsification loop
- contradiction tracking

### Stage 3
- structured evidence system
- traceable reasoning

### Stage 4
- dynamic tool generation
- skill reuse

---

## 10. One-Sentence Thesis

FALCON transforms metagenomic discovery into a **falsification-driven, auditable reasoning system**, where biological hypotheses are not accepted because they look plausible, but because they have **survived systematic attempts to disprove them**.