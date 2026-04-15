---
ingested_at: '2026-04-15T05:24:15.822180+00:00'
locked: false
source: sources/2026/04/48b877f1aa1a-anthropics-project-glasswingrestricting-claude-mythos-to-security-researcherssou.md
  Claude Mythos to security researchers—sounds necessary to me.md
source_hash: 48b877f1aa1a06fa60b0ec7159ceac5bb3d5de775863e5efb1136add8e65b933
title: Anthropic's Project Glasswing — restricting Claude Mythos to security researchers
---

# Anthropic's Project Glasswing — restricting Claude Mythos to security researchers

## Summary

A 2026-04-07 blog post by [[Simon Willison]] reacting to [[Anthropic]]'s decision *not* to generally release its newest frontier model, [[Claude Mythos Preview]], and to instead distribute it only to a curated set of defensive-security partners under the newly announced [[Project Glasswing]]. Willison reads the move as credibly cautious rather than marketing: Anthropic reports that Mythos Preview has already found thousands of high-severity vulnerabilities in every major OS and browser, including working exploits on FreeBSD, Linux privilege escalation, and a full browser exploit chaining four vulnerabilities. The post situates the release against a broader industry shift that Willison was already tracking — [[Greg Kroah-Hartman]], [[Daniel Stenberg]], and [[Thomas Ptacek]] all reporting that [[Autonomous vulnerability research]] by LLM agents has moved past the "AI slop" phase into producing real, actionable security findings. Partners include AWS, Apple, Microsoft, Google, and the Linux Foundation; the program includes $100M in usage credits and $4M in donations to open-source security orgs.

## Key Claims

- [[Anthropic]] is withholding general availability of [[Claude Mythos Preview]] (a model "similar to Claude Opus 4.6") because its offensive-security capabilities are judged too dangerous to release broadly.
- [[Project Glasswing]] is the gated preview program: restricted access for defensive use (local vulnerability detection, black-box binary testing, endpoint hardening, pen-testing), with partners including AWS, Apple, Microsoft, Google, and the Linux Foundation.
- Capability claims from the system card and [[Anthropic]]'s Red Team blog: chained 4-vulnerability browser exploit with JIT heap spray escaping renderer + OS sandboxes; autonomous local privilege escalation on Linux and others via race conditions and KASLR bypass; RCE on FreeBSD NFS via a 20-gadget ROP chain split across packets.
- Comparative benchmark: on a Firefox 147 JS-engine exploit task where [[Opus 4.6]] produced working exploits 2 / several-hundred attempts, Mythos Preview produced 181 working exploits plus 29 additional register-control cases.
- Willison found concrete confirmation in public artifacts: the OpenBSD 7.8 errata 025 (2026-03-25) patches a TCP SACK kernel crash whose surrounding code is 27 years old — matching [[Nicholas Carlini]]'s on-camera claim about a "27-year-old OpenBSD bug."
- Quoted corroboration of the shift:
  - [[Greg Kroah-Hartman]] (Linux kernel): reports moved "a month ago" from AI slop to real, high-quality findings.
  - [[Daniel Stenberg]] (curl): "security report tsunami" — many good reports, hours per day triaging.
  - [[Thomas Ptacek]]: "Vulnerability Research Is Cooked" (2026-03-30), following a podcast with [[Nicholas Carlini]].
- Willison's assessment: "Saying 'our model is too dangerous to release' is a great way to build buzz around a new model, but in this case I expect their caution is warranted."
- [[Anthropic]] signals the longer-term plan: ship new cybersecurity safeguards with an upcoming Opus-class model (not Mythos itself), then gradually extend availability as detection/block safeguards mature.

## Connections

- **Author**: [[Simon Willison]].
- **Model & program**: [[Claude Mythos Preview]], [[Project Glasswing]], [[Anthropic]].
- **Prior model referenced**: [[Opus 4.6]].
- **Security researchers cited**: [[Nicholas Carlini]], [[Greg Kroah-Hartman]], [[Daniel Stenberg]], [[Thomas Ptacek]].
- **Themes**: [[Autonomous vulnerability research]], [[AI safety]], [[CBRN misuse]] (adjacent risk category — Mythos sits in the "cyber" equivalent).
- **Companion source in this wiki**: the [[Claude Mythos Preview System Card]] is the primary document behind the claims Willison quotes.

## Sources
- URL: https://simonwillison.net/2026/Apr/7/project-glasswing/
- Archive: [anthropics-project-glasswingrestricting-claude-mythos-to-security-researcherssou.md](sources/2026/04/48b877f1aa1a-anthropics-project-glasswingrestricting-claude-mythos-to-security-researcherssou.md)
