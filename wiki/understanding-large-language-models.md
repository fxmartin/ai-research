---
ingested_at: '2026-04-15T05:51:37.068006+00:00'
locked: false
source: /Users/fxmartin/dev/ai-research/wiki/raw/Understanding Large Language Models.md
source_hash: 84139e72521584a892b185cfa555445c1cd1d5a5bbb4dc448325aaf8713a52dc
title: Understanding Large Language Models
---

# Understanding Large Language Models

## Summary

A 2023-04-16 primer by [[Sebastian Raschka]] — a curated reading list and narrative arc that walks a machine-learning practitioner from the original Transformer paper up through the alignment-era LLMs of early 2023. The piece is organized into four threads: architecture and tasks, [[Scaling laws]] and efficiency, alignment, and [[RLHF]]. It predates the modern MoE / MLA / sliding-window wave (see [[The Big LLM Architecture Comparison]] for that), so it's useful today mainly as a clean intellectual history — the "pre-frontier" map of how LLMs got to where they are.

## Key Claims

- **Scope**: a reading list more than a tutorial — Raschka selects the papers that a newcomer should read, in the order that makes the lineage legible.
- **Architecture thread**: [[Transformer architecture]] roots (Vaswani et al., BERT, GPT), with an emphasis on why the encoder/decoder split shapes the tasks a model is good at.
- **Scaling thread**: the Kaplan / Chinchilla [[Scaling laws]] papers — why compute, parameters, and tokens are a tightly-coupled triad, and why "more parameters" stopped being the right knob after Chinchilla.
- **Efficiency thread**: techniques for getting more from fixed compute — quantization, mixture-of-experts (early work predating today's large-scale deployment), distillation. This is where the book scales from "what" to "how practical."
- **Alignment thread**: InstructGPT and the move from raw next-token prediction to instruction-tuned models — the missing piece that turned research demos into products.
- **[[RLHF]]**: framed as the alignment workhorse circa 2023; the article walks through reward modeling and PPO-style fine-tuning.
- **Vantage point**: written *before* GPT-4 was broadly characterized, before Claude 2, before the open-weight tsunami. The gap between its frame and [[The Big LLM Architecture Comparison]] is the best way to see how fast the field moves.

## Connections

- **Author**: [[Sebastian Raschka]].
- **Core concept**: [[Transformer architecture]].
- **Themes**: [[Scaling laws]], [[RLHF]], [[AI alignment]].
- **Follow-up by the same author**: [[The Big LLM Architecture Comparison]] (2025-07 — modern architecture survey), [[Components of A Coding Agent]] (2026-04 — harness layer).
- **In this wiki**: useful baseline for readers approaching frontier-model cards ([[Claude Opus 4.6 System Card]], [[Claude Mythos Preview System Card]]) without a prior LLM background.

## Sources
- [Understanding Large Language Models](wiki/raw/Understanding Large Language Models.md) (https://magazine.sebastianraschka.com/p/understanding-large-language-models)
