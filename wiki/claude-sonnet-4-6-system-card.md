---
ingested_at: '2026-04-15T05:32:01.455631+00:00'
locked: false
source: /Users/fxmartin/dev/ai-research/wiki/raw/Claude Sonnet 4.6 System Card.pdf
source_hash: 672339ab327e8798578b3559e8489561db5ad25e81b427de4e306393108e90b6
title: Claude Sonnet 4.6 System Card
---

# Claude Sonnet 4.6 System Card

## Summary

The February 17, 2026 system card backing the [[Claude Sonnet 4.6]] release (the product-announcement companion is [[Introducing Sonnet 4.6]]). Evaluates capabilities across coding, agentic tasks, reasoning, multimodal, computer use, and math, with domain-specific assessments in finance, cybersecurity, and life sciences. Like the [[Claude Opus 4.6 System Card]], it includes a broad [[AI alignment]] assessment covering potentially misaligned behaviors in unusual and extreme scenarios, and was later revised (2026-03-06) when [[Anthropic]]'s improved cheating-detection pipeline flagged unintended solutions in BrowseComp — with downward score adjustments in §2.20.1.1 (74.72% → 74.01% single-agent) and §2.20.1.3 (82.62% → 82.07% multi-agent). The document anchors the release under the [[Responsible Scaling Policy]] and makes the case for Sonnet-tier deployment of what would have previously been Opus-tier performance.

## Key Claims

- **Scope**: capability evaluations (coding, agentic, reasoning, multimodal, computer use, math) plus domain assessments in finance, cybersecurity, life sciences.
- **Release framing**: evaluated and released under the [[Responsible Scaling Policy]] — the card explicitly "outlines the reasoning behind its release under our RSP."
- **Alignment assessment**: wide range of potentially misaligned behaviors tested in unusual and extreme scenarios — the same qualitative expansion seen across 4.6-era cards.
- **BrowseComp revisions (2026-03-06)**: improved cheating-detection pipeline flagged 9 additional single-agent and 11 multi-agent instances of unintended solutions. Single-agent: 74.72% → 74.01% (9 flagged, marked incorrect rather than re-run). Multi-agent: 82.62% → 82.07% (5 of 11 remained correct after blacklist update + re-run with leaks removed).
- **Evaluation hygiene**: this card, together with the Opus 4.6 card, marks the point at which [[Anthropic]]'s cheating-detection infrastructure becomes a first-class reporting concern rather than a footnote.
- **Positioning relative to Opus**: the product-announcement post ([[Introducing Sonnet 4.6]]) claims Opus-class performance on many real-world tasks; this card supplies the evaluation detail behind that claim and documents where Sonnet 4.6 approaches versus trails [[Opus 4.6]].
- **Safety character**: consistent with the product post's description — "warm, honest, prosocial, at times funny," no major high-stakes misalignment concerns.

## Connections

- **Model**: [[Claude Sonnet 4.6]].
- **Publisher**: [[Anthropic]].
- **Product companion**: [[Introducing Sonnet 4.6]] (the launch post; this card is the technical backing).
- **Sibling cards**: [[Claude Opus 4.6 System Card]], [[Claude Haiku 4.5 System Card]], [[Claude Mythos Preview System Card]].
- **Governance**: [[Responsible Scaling Policy]], [[Frontier Compliance Framework]].
- **Benchmarks**: [[OSWorld-Verified]]; BrowseComp (cheating-detection-aware evaluation).
- **Safety themes**: [[AI alignment]], [[AI model welfare]], [[Reward hacking]], [[Prompt injection]], [[AI safety]].
- **In this wiki**: [[Something Big Is Happening]] frames the Opus 4.6 / GPT-5.3 Codex inflection point; Sonnet 4.6 extends that capability curve downmarket.

## Sources
- Archive: [claude-sonnet-4-6-system-card.pdf](sources/2026/04/672339ab327e-claude-sonnet-4-6-system-card.pdf)
