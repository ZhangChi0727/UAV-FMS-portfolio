# Application evidence index

This directory collects the technical evidence that is intended to be read by an external reviewer. It adds
files only; no existing module path has been moved or renamed.

**Status (2026-11-17): skeleton only. No result in this directory has been verified yet.** Each entry below says
what it will contain and what it will not claim. Numbers appear only after they have been re-checked against a
retained artifact.

## What this repository is and is not

- It is a verification platform for a bounded multirotor attitude experiment (baseline B0 v0.2): attitude
  estimation and cascaded control, with systems-engineering models, requirements status and evidence reports.
- B0 as a whole is **not** accepted. See [RESULTS.md](../RESULTS.md) for what has been accepted and what has not.
- No flight, hardware, HIL or broad performance result is claimed.
- The saturation-reachability finding is a negative result and is unresolved: the frozen scenario requires at
  least 0.05 s of saturation, and the recorded runs reach 0.0 s (best of seven candidates 0.025 s). See
  [RESULTS.md](../RESULTS.md).
- The older EKF/UKF, geometric-control, TCN and related modules (`02_estimation/python`, `02_estimation/cpp`,
  `03_control/python`, `04_fault_detection`, `06_safety`, and parts of `01_simulation` and `05_integration`) are
  **legacy scaffolds**. Several are placeholders or `NotImplemented`. They are not evidence.

## Contents

| Entry | Content | State |
|---|---|---|
| [timing_probe_study/](timing_probe_study/README.md) | Scheduler and probe-effect measurement study on a Windows host | In preparation |
| [ml_study/](ml_study/README.md) | Small learned angular-rate forecaster compared against physics baselines on B0 plant data | In preparation; not trained yet |
| [verification_algorithm/](verification_algorithm/README.md) | Pointer to a separate verification-method project | Placeholder |
| [CONTRIBUTIONS.md](CONTRIBUTIONS.md) | Who did what, including AI-agent assistance, and what is unfinished | Draft |

## Reading order for a reviewer

1. This page.
2. [CONTRIBUTIONS.md](CONTRIBUTIONS.md).
3. [RESULTS.md](../RESULTS.md) and the [project charter](../systems_engineering/project_charter.md).
4. The two study folders, once their state changes from "In preparation".

## Conventions

Frames are NED (world) and body FRD, units are SI, quaternions are scalar-first Hamilton. A reproduction command is
listed only after it has been executed on a clean checkout, together with the observed result.
