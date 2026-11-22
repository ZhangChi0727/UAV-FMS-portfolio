# Requirements

This directory is the single systems-engineering source for the project. It is
written in [StrictDoc](https://strictdoc.org) `.sdoc` format and is the only tool
used for requirements, status and traceability.

| File | Content |
|---|---|
| [b0.sdoc](b0.sdoc) | B0-REQ-0001 to B0-REQ-0030: attitude estimation and cascaded control |
| [edge.sdoc](edge.sdoc) | EDG-REQ-0001 to EDG-REQ-0012: distributed edge AI for bridge inspection |

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

Requirement IDs are never renumbered. Retired text is kept in git history at the
tag `pre-surgery-2026-11-22`.

## Scope notes

- Civil bridge inspection only. Imagery must be public or synthetic with its
  licence recorded.
- No hardware is available. Every measurement is a development-host (Intel i9 CPU,
  NVIDIA RTX 4060 GPU) result and must be labelled as such.
- Numerical acceptance thresholds for edge-inference requirements are not defined
  yet. They are set in a separate, reviewed design note before any measurement is
  claimed.

## Commands

From the repository root, with the virtual environment active:

```sh
strictdoc export requirements --output-dir requirements/build
```

The generated HTML is written to `requirements/build/html` and is not committed.
