# Estimation

B0 requires basic quaternion attitude fusion. Existing Python EKF/UKF and C++ EKF files remain EXT-NAV scaffolds. The 16-element nominal / 15-element error-state contract remains in architecture.md; placeholder code does not satisfy it. VO is optional. Run navigation pytest inside python/.

See [baseline](../systems_engineering/development_baseline.md), [architecture](../systems_engineering/models/architecture.md) and [extension registry](../docs/roadmap.md).

Status: planned; existing scaffold paths are retained for compatibility.
