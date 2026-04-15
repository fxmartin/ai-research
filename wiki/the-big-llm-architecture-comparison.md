---
ingested_at: '2026-04-15T05:51:36.344764+00:00'
locked: false
source: /Users/fxmartin/dev/ai-research/wiki/raw/The Big LLM Architecture Comparison.md
source_hash: 944cdcddb5308ff370c2f05390882bd4afd5ed2e1201af2f9e56acf9f90727ce
title: The Big LLM Architecture Comparison
---

# The Big LLM Architecture Comparison

## Summary

A July 2025 survey by [[Sebastian Raschka]] walking through the structural design choices of twelve then-current open(-weight) LLM families — [[DeepSeek V3]]/R1, [[OLMo 2]], [[Gemma 3]], [[Mistral Small 3.1]], [[Llama 4]], [[Qwen3]], [[SmolLM3]], [[Kimi K2]] (incl. Thinking), [[GPT-OSS]], [[Grok 2.5]], [[GLM-4.5]], and Qwen3-Next. Raschka's frame is that despite the marketing, the underlying [[Transformer architecture]] has stayed remarkably stable since GPT-2 / Llama 1; the interesting differentiation lives in a small set of well-defined levers: how attention is factorized ([[Multi-Head Latent Attention]], [[Sliding window attention]], NoPE), how sparsity is introduced ([[Mixture-of-Experts]] routing and expert count), and where/how normalization is placed (pre- vs post-norm, QK-Norm). The article is more of a reference map than a benchmark post — it pulls each architecture down to the *changed block* relative to the reference Transformer.

## Key Claims

- **Architectural stability thesis**: across 2022→2025 the core [[Transformer architecture]] barely moves. What changes is *where* the tweaks land — attention factorization, sparsity, and normalization placement dominate the differentiation.
- **DeepSeek V3/R1** introduces [[Multi-Head Latent Attention]] (MLA — compresses K/V into a low-rank latent to shrink KV cache) plus a fine-grained [[Mixture-of-Experts]] routing scheme with many small experts. Sparsity is now a default, not a specialty.
- **OLMo 2**: a deliberately reproducible open model; notable for [[Transformer architecture|normalization-layer placement]] choices (§2.1) and **QK-Norm** (applying layer-norm to Q/K before attention) for training stability.
- **Gemma 3**: mixes local [[Sliding window attention]] with periodic global attention layers; reworked normalization placement; Gemma 3n adds a compact variant.
- **Mistral Small 3.1 / Llama 4**: largely incremental — the article treats them as calibrations on the Llama-style dense path, with Llama 4 extending toward [[Mixture-of-Experts]].
- **Qwen3** ships both a dense variant and an MoE variant under the same name — Raschka uses this as the clearest side-by-side of the "same recipe, add sparsity" move.
- **SmolLM3**: notable for **NoPE** — *no* positional embeddings at all (§7.1), leaning on attention and data to carry position implicitly. A live experiment in whether [[RoPE]] is load-bearing or conventional.
- **Kimi K2 / K2 Thinking**: frontier-scale MoE; "Thinking" is the inference-time-reasoning variant following the DeepSeek R1 lineage.
- **GPT-OSS**: OpenAI's open-weight release; Raschka reads it as "standard-recipe Transformer with a clean MoE" — confirming that even frontier labs converge on the same knobs.
- **Grok 2.5 / GLM-4.5 / Qwen3-Next**: three further points on the same map — MoE variants with different routing details and expert counts, all recognizably the same base architecture as the others.
- **Takeaway**: if you understand MLA, MoE routing, sliding-window vs global attention, NoPE, and normalization placement, you can "read" any 2024–2025 model's architecture diagram quickly.

## Connections

- **Author**: [[Sebastian Raschka]].
- **Core concept**: [[Transformer architecture]].
- **Attention levers**: [[Multi-Head Latent Attention]], [[Sliding window attention]], [[RoPE]].
- **Sparsity lever**: [[Mixture-of-Experts]].
- **Model families covered**: [[DeepSeek V3]], [[OLMo 2]], [[Gemma 3]], [[Mistral Small 3.1]], [[Llama 4]], [[Qwen3]], [[SmolLM3]], [[Kimi K2]], [[GPT-OSS]], [[Grok 2.5]], [[GLM-4.5]].
- **In this wiki**: complements [[Understanding Large Language Models]] (Raschka's earlier 2023 primer on the same machinery) and [[Components of A Coding Agent]] (harness-layer companion to this model-layer survey).

## Sources
- URL: https://magazine.sebastianraschka.com/p/the-big-llm-architecture-comparison
- Archive: [the-big-llm-architecture-comparison.md](sources/2026/04/944cdcddb530-the-big-llm-architecture-comparison.md)
