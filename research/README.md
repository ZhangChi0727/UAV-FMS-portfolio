# Research packages

The platform may support multiple papers. Engineering releases and publication
decisions have independent completion criteria. The following are candidates,
not commitments to novelty or a paper count.

| Package | Question | Dependencies | Required evidence |
|---|---|---|---|
| RP-EST | Can estimation-aware control/recovery improve behavior during sensor degradation? | Relevant EXT-NAV/EXT-HEALTH; EXT-FLIGHT for trajectory claims | Classical baselines, ablations, nominal regression, recovery metrics |
| RP-TIME | How do delay, jitter and computation constraints affect control, and can they be mitigated? | B0, EXT-EMBED | Measured timing, matched simulation assumptions, compensation comparison |
| RP-VERIFY | What verification semantics and evidence remain reusable across execution environments? | Local verification, EXT-VERIFY; EXT-HIL if claimed | Adaptation cost, seeded-defect detection, semantic differences and limits |
| RP-BENCH | Which reproducible scenarios expose meaningful failure boundaries of existing methods? | Mature relevant extensions | Coverage rationale, multiple baselines, dataset provenance and external reuse procedure |

## Package activation contract

Before activation, create a package document using [the template](package_template.md).
Record literature searches, a narrow gap, hypotheses and falsifiers, required platform
version, comparators, metrics, trial design, data split policy, resources, and exit rules.
At most one exploration is active. None is activated by this planning revision.

## Publication boundaries

Each paper must answer an independently defensible question with sufficient methods
and evidence. Reusing a platform is allowed; disclose shared code, data, experiments,
and companion publications. Simulation, board execution and HIL are not automatically
separate papers. Freeze platform revision, experiment configuration, seeds, raw outputs
and analysis for each submission. Do not claim novelty from integration alone.

Stable validated capabilities may return to common modules. Experimental variants
stay within a package boundary and must not silently change released baseline results.

## Existing literature

The July 2026 pilot record is retained under [literature](../literature/README.md).
CLM-001 and CLM-002 inform RP-EST; CLM-003 informs RP-BENCH and RP-VERIFY.
These are candidates requiring new searches, not established contributions.
Timing and verification-transfer literature need separate search coverage.
