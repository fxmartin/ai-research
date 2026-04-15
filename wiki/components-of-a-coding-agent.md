---
ingested_at: '2026-04-15T05:36:28.526633+00:00'
locked: false
source: /Users/fxmartin/dev/ai-research/wiki/raw/Components of A Coding Agent.md
source_hash: bed829db41afcc5836d2d33b967ec23742c9807dd6cb5880f2f819fe12fa31aa
title: Components of A Coding Agent
---

# Components of A Coding Agent

## Summary

A 2026-04-04 reference piece by [[Sebastian Raschka]] laying out the design of modern coding agents — "agentic harnesses" like [[Claude Code]] and [[Codex CLI]] that wrap an LLM in a surrounding system to make it materially more effective at real software work than the same model used in plain chat. Raschka decomposes a [[Coding agent harness]] into six building blocks (live repo context, prompt shape with [[Prompt cache]] reuse, structured tools/validation/permissions, context-bloat management, session memory/resumption, and [[Subagent delegation]]), and maps each to concrete harness primitives (`WorkspaceContext`, `build_prefix`, `build_tools`, `clip`, `SessionStore`, `tool_delegate`). The central claim is that recent practical LLM gains come as much from harness engineering as from model weights — i.e. that the "agent" is a first-class engineering artifact, not a thin wrapper. He frames LLM → reasoning model → agent as "engine → beefed-up engine → harness around the engine."

## Key Claims

- **Thesis**: in practice, harness design (repo context, tool surface, prompt-cache stability, memory, long-session continuity) contributes as much to coding-agent quality as the underlying model. [[Claude Code]] and [[Codex CLI]] outperform the same models in a plain chat UI primarily because of harness, not weights.
- **Terminology split**: LLM = next-token model; reasoning model = LLM trained/prompted to spend more inference compute on intermediate reasoning; agent = control loop that decides what to inspect, which tools to call, how to update state, when to stop.
- **Component 1 — Live Repo Context (`WorkspaceContext`)**: the harness exposes the current working tree (file listing, open files, recent diffs) so the model reasons about the actual repo, not a frozen snapshot.
- **Component 2 — Prompt shape + cache reuse (`build_prefix`, `memory_text`, `prompt`)**: deliberately stable prefix structure so [[Prompt cache]] hits are maximized across turns; memory text is kept in the cacheable prefix.
- **Component 3 — Structured tools, validation, permissions (`build_tools`, `run_tool`, `validate_tool`, `approve`, `parse`, `path`, `tool_*`)**: tools are typed, validated, and permissioned. [[Agentic tool use]] is the primary lever by which the model acts on the world; bad tool design silently caps agent quality.
- **Component 4 — Context reduction & output management (`clip`, `history_text`)**: explicit strategies for clipping tool outputs and trimming history so the context window isn't silently consumed by low-value tokens.
- **Component 5 — Transcripts, memory, resumption (`SessionStore`, `record`, `note_tool`, `ask`, `reset`)**: session state is persisted and resumable. Long-running coding tasks survive interruption and restart without losing context.
- **Component 6 — Delegation with bounded subagents (`tool_delegate`)**: [[Subagent delegation]] is treated as a first-class harness feature — the main agent can spawn bounded subagents for well-scoped tasks, protecting its own context budget.
- **Comparison**: the piece closes by comparing the author's own "Mini Coding Agent" and a reference design called OpenClaw against production harnesses; the six-component breakdown maps cleanly across all of them.

## Connections

- **Author**: [[Sebastian Raschka]].
- **Core concept**: [[Coding agent harness]].
- **Production harnesses**: [[Claude Code]], [[Codex CLI]].
- **Harness primitives as concepts**: [[Prompt cache]], [[Agentic tool use]], [[Subagent delegation]].
- **Model layer context**: [[AI agents]], [[Knowledge work automation]].
- **In this wiki**: connects to [[Something Big Is Happening]] (which describes the *effect* of harness-driven agents — "walk away for four hours, come back to finished work") and to [[Introducing Sonnet 4.6]] / [[Claude Opus 4.6 System Card]] (which benchmark *models* but are deployed through exactly the kind of harness Raschka dissects here).

## Sources
- [Components of A Coding Agent](wiki/raw/Components of A Coding Agent.md) (https://magazine.sebastianraschka.com/p/components-of-a-coding-agent)
