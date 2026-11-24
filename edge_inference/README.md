# EDGE: bridge inspection model compression

The active proposed requirements are EDG-REQ-0034–0041. These files are scaffolding,
not a trained detector, functional compression pipeline, or benchmark. No accuracy,
latency, board or flight results are claimed.

- configs/: reserved for future configuration.
- src/: reserved for future model, compression and profiling implementation.
- logs/TEMPLATE.md: experiment record template.
- data/ and models/: local artifacts, not committed.

No model code, configuration or end-to-end CLI is implemented. CPU thread limits
alone do not emulate an ARM or Jetson device. Record the actual host as development-host. Datasets and weights
are not included; verify licences and class mappings before use.
