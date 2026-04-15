---
ingested_at: '2026-04-15T16:27:54.018483+00:00'
locked: false
source: sources/2026/04/48c941dbdc10-labor-market-impacts-of-ai-a-new-measure-and-early-evidence.pdf
source_hash: 48c941dbdc1053456ec72f893c6a27630559507d3882895bb036d034b6972450
title: 'Labor Market Impacts of AI: A New Measure and Early Evidence'
---

# Labor Market Impacts of AI: A New Measure and Early Evidence

## Summary

March 2026 [[Anthropic Economic Index]] "nowcasting" report by [[Maxim Massenkoff]] and [[Peter McCrory]] that introduces **[[Observed Exposure]]** — an occupation-level AI-displacement-risk measure combining theoretical LLM capability (from [[Eloundou et al. 2023]]) with real-world Claude usage, weighted to emphasize *automated* (versus augmentative) and *work-related* use. The authors argue that prior "offshorability" forecasts over-predicted disruption that did not arrive, and position observed exposure as a measure best used *before* effects are unmistakable. Early findings: AI is far from its theoretical capability ceiling (Claude covers only ~33% of Computer & Math tasks, vs. ~94% theoretically feasible); highly-exposed occupations are projected by the BLS to grow less through 2034; most-exposed workers skew older, female, more educated, higher-paid. Crucially, the authors find **no systematic increase in unemployment** for highly-exposed workers since late 2022, with only suggestive evidence of slower hiring of *younger* workers in exposed occupations.

## Key Claims

- **Observed Exposure = theoretical capability × observed usage**, weighted by automation share, work-relatedness, and task time-share within a role. Fully-automated use gets full weight; augmentative use gets half weight.
- **Three data sources:** [[O*NET]] (task taxonomy for ~800 US occupations), [[Anthropic Economic Index]] (Claude usage), and [[Eloundou et al. 2023]]'s β metric (1 = LLM can 2× speed; 0.5 = needs additional tooling; 0 = not feasible).
- **Capability ≠ diffusion.** 97% of observed Claude tasks fall into Eloundou's theoretically-feasible buckets (β ≥ 0.5), and β=1 tasks alone account for 68% of Claude usage — yet coverage of the possible task space remains a minority. Gaps trace to model limitations, legal constraints, software dependencies, and human-verification requirements.
- **Top 10 most exposed occupations** are led by Computer Programmers (~75% coverage) and Customer Service Representatives, with Data Entry Keyers in the top ranks — consistent with the observation that coding is Claude's dominant use case.
- **Forecast correlation with BLS projections.** Occupations with higher observed exposure have lower BLS-projected growth through 2034 — one of the few cases where the metric and an independent official forecast agree directionally.
- **Demographic skew of exposure.** Most-exposed workers are disproportionately older, female, more educated, and higher-paid — a departure from the usual "vulnerable-worker" framing attached to automation risk.
- **No macro unemployment signal yet.** Aggregate unemployment data for highly-exposed workers shows no systematic increase since late 2022. The only suggestive finding is slower hiring of younger workers in exposed roles — an early, narrow signal worth tracking.
- **Framing.** The framework is most valuable when effects are ambiguous — more like the internet or the China trade shock than COVID. The authors commit to revisiting these analyses periodically.

## Connections

- **Publisher / program**: [[Anthropic]], via the [[Anthropic Economic Index]].
- **Authors**: [[Maxim Massenkoff]], [[Peter McCrory]].
- **Methodological dependencies**: [[Eloundou et al. 2023]] (theoretical β capability metric), [[O*NET]] (task taxonomy), [[BLS Occupational Outlook]] (external growth forecasts).
- **Introduces**: [[Observed Exposure]] — an occupation-level measure combining capability, usage, automation share, and time-fraction.
- **Themes**: [[Labor market disruption]], [[Knowledge work automation]].
- **Related wiki**: [[Dario Amodei — Machines of Loving Grace]] (frames AI labor impact as compressed-21st-century upside); [[AI 2027]] (scenario-style forecast complementing this empirical nowcasting). The nowcasting paper's posture is explicitly *empirical and cautious* where AI 2027 is *scenario and bold*.

## Sources
- Archive: [labor-market-impacts-of-ai-a-new-measure-and-early-evidence.pdf](sources/2026/04/48c941dbdc10-labor-market-impacts-of-ai-a-new-measure-and-early-evidence.pdf)
