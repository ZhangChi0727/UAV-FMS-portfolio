# Repository working rules

Read README.md and 07_docs/project_charter.md, development_baseline.md,
architecture.md and roadmap.md before implementation.
B0 v0.2 is the active planning baseline: attitude estimation and cascaded control.
Navigation, geometric-control and TCN files remain legacy scaffolds.
Research candidates do not automatically expand B0.

## Hard rules

- Do not invent or renumber NAV-REQ-*, CTL-REQ-* or FDI-REQ-* identifiers.
- Run pytest inside each track; root collection is unsupported.
- Do not invent numerical/SIL/HIL/Monte Carlo results; cite retained artifacts.
- Keep truth out of estimator/controller inputs except explicit initialization.
- Preserve NED/body, SI and scalar-first Hamilton quaternion conventions.
- Preserve user changes and module paths unless a scoped migration needs them.
- Completed checks are mandatory; skips/xfails are not implementation evidence.
- Distinguish replay, board execution, real-time closed-loop HIL and flight.
- Keep documentation technical and research-focused.

## Environment

Python 3.11+ and C++17 are intended. Detect installed tools; do not assume a
specific cloud image. Use a virtual environment. Root CMake targets the legacy
EXT-NAV EKF, not B0 control. Eigen3/Catch2 and optional pybind11 are dependencies.
The legacy Catch2 Approx qualification issue remains pending; report only
actually executed build results. MATLAB/PyTorch are extension-specific.

## Research and management

Use literature/protocol.md; preserve historical pilot records. Do not commit
credentials, copyrighted full texts, private notes, generated exports or notebook
outputs. Claim-critical evidence needs source locators. Activate research through
research/package_template.md. Keep one primary engineering increment and at most
one active exploration. Issues own execution state; roadmap owns scope;
RESULTS.md owns verified outcomes. Each PR records actual validation.
