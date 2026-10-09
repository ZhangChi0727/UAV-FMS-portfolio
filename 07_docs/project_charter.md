# Project charter

Version: 0.2 | Adopted: 2026-10-09 | Owner: Chi Zhang

## Purpose

Develop and verify a bounded UAV control and navigation system through independent
algorithm implementation, simulation integration, and optional embedded execution.
The platform supports reproducible engineering experiments and multiple independent
research questions. A publication is not a prerequisite for an engineering release.

## Product boundaries

The common platform owns plant/sensor models, estimation and control interfaces,
execution adapters, scenario evaluation, and reproducible evidence. It does not
aim to replace a complete autopilot, simulator, or generic verification framework.

The first release is B0, the attitude closed loop defined in
[the development baseline](development_baseline.md).
Extensions are optional capability packages, not a mandatory sequence.
Research packages select only the capabilities needed to test their hypotheses.

## Relationship to other verification systems

A reusable verification suite owns domain-neutral execution, traceability, and
evidence mechanisms. This repository owns UAV-specific scenarios, signal semantics,
adapters, metrics, and oracles. Local verification must work independently.
Extract shared mechanisms only after concrete reuse is demonstrated. No dependency
on completion of another repository is imposed on B0.

## Success and stopping rules

- Engineering: a bounded version is reproducible, explainable, tested, and released.
- Extensions: each has a dependency list, acceptance criteria, and independent exit.
- Research: each has an explicit question, prior-art comparison, experimental design,
  and falsification/termination criteria.
- Stop expanding a release when its agreed acceptance criteria are met.
- One primary engineering increment and at most one active research exploration.
- No promise of algorithm novelty, publication count, certification, or flight safety.

## Change decision

The former parallel EKF/UKF, geometric/LQR, and TCN portfolio is reorganized around
one shared closed loop. Existing navigation contracts are retained for EXT-NAV.
C++ control, basic estimation, and deterministic verification take priority.
PX4, embedded execution, fixed-wing control, and research are separately gated.
See [the roadmap](roadmap.md) for the authoritative capability registry.
