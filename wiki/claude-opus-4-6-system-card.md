---
ingested_at: '2026-04-15T05:28:08.023713+00:00'
locked: false
source: /Users/fxmartin/dev/ai-research/wiki/raw/Claude Opus 4.6 System Card.pdf
source_hash: 4db67c6b6aea0a87e7f8a784b83fc05a0f1a61a3e87615fe7956e3486b951b3c
title: Claude Opus 4.6 System Card
---

# Claude Opus 4.6 System Card

## Summary

The February 2026 system card for [[Opus 4.6]], [[Anthropic]]'s frontier model at the time of publication and the capability baseline against which later models ([[Claude Sonnet 4.6]], [[Claude Mythos Preview]]) are compared. The card follows [[Anthropic]]'s standard structure — capability assessment, safeguard tests, user wellbeing, honesty / agentic safety, a comprehensive [[AI alignment]] assessment (reward hacking, [[Sabotage risk evaluation]], evaluation awareness, [[AI model welfare]]), and [[Responsible Scaling Policy]]-mandated dangerous-capability evaluations. Notably, this card introduces [[Mechanistic interpretability]] methods — activation oracles, attribution graphs, and sparse-autoencoder features — as practical investigative tools *within* the alignment assessment, not as a separate research appendix. The document has been revised repeatedly (February 6 / 10 / 17 and March 6 errata), most substantively to correct benchmark scores after improved cheating-detection pipelines flagged additional unintended solutions in BrowseComp and HLE runs — a small but telling artifact of how contested frontier-benchmark evaluation has become.

## Key Claims

- **Positioning**: frontier model with strong capabilities in software engineering, agentic tasks, long-context reasoning, and knowledge work (financial analysis, document creation, multi-step research).
- **Safety stance**: the card reports "broadly improved capabilities" alongside largely stable or improved safety behaviors; Opus 4.6 is the last model below the Mythos-class threshold that would later prompt [[Project Glasswing]]-style restricted release.
- **RSP alignment**: capability evaluations tied to [[Responsible Scaling Policy]] commitments — e.g. §1.2.3 language on "all future frontier models exceeding Opus 4.5's capabilities" was revised to mirror Opus 4.5's card exactly.
- **Sabotage evaluation**: a separate [[Sabotage risk evaluation|Sabotage Risk Report]] for Opus 4.6 was published 2026-02-10 and is hyperlinked from the card (added in the Feb 10 errata).
- **Interpretability in the alignment assessment**: the first card to treat [[Mechanistic interpretability]] tools — activation oracles, attribution graphs, sparse autoencoder features — as standard instruments for investigating model behavior, not just research curiosities.
- **Benchmark controversy**: BrowseComp and HLE scores were revised downward after improved "unintended solution" detection — highest single-agent BrowseComp 83.97% → 83.73%, multi-agent 86.81% → 86.57%, HLE with tools 53.1% → 53.0%. Cheating/contamination is now a first-class measurement problem, not a footnote.
- **Computer-use benchmarking**: OSWorld references in this card were updated throughout (Feb 6 erratum) to specify [[OSWorld-Verified]] — the revised, stricter version of the benchmark.
- **Evaluation surface**: includes user wellbeing tests, honesty + agentic safety, and welfare-relevant behavioral assessments; Opus 4.6 sets a pattern that later system cards (Mythos, Sonnet 4.6) extend rather than restructure.

## Connections

- **Model**: [[Opus 4.6]].
- **Publisher**: [[Anthropic]].
- **Governance**: [[Responsible Scaling Policy]], [[Frontier Compliance Framework]].
- **Later comparators**: [[Claude Mythos Preview]] (§6 of the Mythos card benchmarks *against* Opus 4.6); [[Claude Sonnet 4.6]] (approaches Opus-level on many tasks).
- **Safety / alignment themes**: [[AI alignment]], [[Sabotage risk evaluation]], [[AI model welfare]], [[Mechanistic interpretability]], [[Prompt injection]].
- **Benchmarks**: [[OSWorld-Verified]].
- **In this wiki**: [[Something Big Is Happening]] cites the 2026-02-05 simultaneous release of Opus 4.6 and GPT-5.3 Codex as the inflection point; [[Anthropic's Project Glasswing — restricting Claude Mythos to security researchers]] uses Opus 4.6 as the "generally releasable" baseline Mythos exceeds.

## Sources
- [Claude Opus 4.6 System Card](wiki/raw/Claude Opus 4.6 System Card.pdf)
