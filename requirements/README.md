# Requirements

This directory is the single systems-engineering source for the project. It is
written in [StrictDoc](https://strictdoc.org) `.sdoc` format and is the only tool
used for requirements, status and traceability.

| File | Content |
|---|---|
| [b0.sdoc](b0.sdoc) | B0-REQ-0001 to B0-REQ-0030: attitude estimation and cascaded control |
| [edge.sdoc](edge.sdoc) | EDG-REQ-0001 to EDG-REQ-0033: distributed edge AI for bridge inspection (all proposed, not frozen) |

## Field definitions

- `STATUS` is the lifecycle state of the statement. `frozen` means the text is
  fixed at the tag `req-freeze-*` created after review. `proposed` means the text
  is not yet frozen.
- `STATE` is the implementation state, assessed from repository content.
  `implemented` means code and a unit test are present in the active tree; it is
  not closed-loop verification. `partial` means some but not all acceptance
  content is present. `planned` means no executed code exists in the active tree.
  No requirement is marked as verified by a system-level test.
- `EVIDENCE` lists file paths or states that none exists yet.

The B0 StrictDoc statements in this migration are `proposed` and await review
and a future freeze; no `req-freeze-*` tag is asserted here. This lifecycle
status does not revoke historical G0 or component approvals.

Requirement IDs are never renumbered. Retired text is kept in git history at the
tag `pre-surgery-2026-11-22` and at the
[archived commit](https://github.com/ZhangChi0727/UAV-FMS-portfolio/tree/d102a9e018c9b9b0b0e5385f509c2fb2c3adffbd).

## Scope notes

- Civil bridge inspection only. Imagery must be public or synthetic with its
  licence recorded.
- No hardware is available. Every measurement is a development-host (Intel i9 CPU,
  NVIDIA RTX 4060 GPU) result and must be labelled as such.
- Normative edge-inference acceptance definitions are maintained in `edge.sdoc`.
  Run configurations and technical explanations reference those definitions;
  they do not constitute a separate normative authority.

## Commands

From the repository root, with the virtual environment active:

```sh
strictdoc export requirements --output-dir requirements/build
```

The generated HTML is written to `requirements/build/html` and is not committed.
