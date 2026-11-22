# EDGE track: learning modules

Goal: place vision-language and language-model inference across onboard, edge and
cloud resources for UAV bridge inspection, and measure the trade-offs by replay.
Requirements are in [requirements/edge.sdoc](../requirements/edge.sdoc).

No module below has code yet. A module is added with its tests and its
requirement status in the same change.

| Module | Learning goal | External interface | Internal logic | Requirements |
|---|---|---|---|---|
| M0 Environment and harness | Reproducible runs | config file, seed, run record | fixed versions, seeded runs, raw output files | EDG-REQ-0003, 0008 |
| M1 Instruction to task | Structured output from a language model | instruction text to task record (JSON schema) | constrained decoding or rule baseline; schema check | EDG-REQ-0001, 0010 |
| M2 Image to finding | Vision-language inference with abstention | image and task to finding (class, region, confidence, abstain) | model inference; threshold on confidence | EDG-REQ-0002, 0003 |
| M3 Profiling | Latency and memory measurement | model, precision, input to per-run timing and memory | warm-up, repeated runs, percentiles from raw data | EDG-REQ-0004, 0009 |
| M4 Placement policy | Deterministic placement under constraints | task, device profile, link state to placement | rule-based function compared with fixed and greedy baselines | EDG-REQ-0005, 0012 |
| M5 Fallback and replay | Behaviour under link loss and budget violation | event trace to logged decisions | injected events; seeded replay | EDG-REQ-0006, 0007 |

## Constraints

- Development PC only (Intel i9 CPU, NVIDIA RTX 4060 GPU). Every result is labelled
  with its host.
- Imagery is public or synthetic, with the licence recorded.
- The track does not depend on the B0 control modules (EDG-REQ-0011).
