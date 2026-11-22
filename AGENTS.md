# Repository working rules

Read README.md and requirements/README.md before changing anything.

## Rules

- requirements/*.sdoc (StrictDoc) is the only systems-engineering source. Do not
  add other requirement, verification or status documents.
- Never renumber or reuse requirement IDs. Add new IDs only by appending to the
  relevant .sdoc file.
- Keep the NED/body frames, SI units and scalar-first Hamilton quaternions.
- Keep truth out of estimator and controller inputs except explicit initialization.
- Run pytest inside each track directory; the repository root is not a test root.
- Report only commands that were executed, with their actual results. Skips and
  expected failures are not evidence.
- Label every measurement with its host (development PC, edge device, flight).
  No hardware, flight or closed-loop performance claim without retained raw data.
- Do not commit credentials, personal application materials, private notes or
  generated outputs (requirements/build, build/).
- One coherent change per pull request. The PR description lists the commands run
  and their results.
