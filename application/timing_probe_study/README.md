# Scheduler and probe-effect study

**State: draft for author review.** See [report.md](report.md). Its numbers come from a read-only re-check of the
retained evidence in `research/scheduler_holdout`, `research/paired_scheduler`, `research/external_transfer` and
`research/pubsub_transfer`; they are pending author sign-off. The periodic-service stress count in
`research/external_transfer/service` matches the retained audit but was not re-derived.

## Question

Whether a frozen rule can predict, from a small set of timing parameters, whether a periodic task set meets its
deadlines on a general-purpose host, and how the act of measuring (the probe) changes the outcome.

## Scope limits that will be stated in the report

- The host is Windows. There is no board execution and no independent hardware observer.
- The measurement windows were chosen near a critical phase on purpose. The results therefore cannot estimate a
  natural failure rate.
- A dedicated solver, if used, is not claimed as a contribution. No novelty claim is made.
- No conclusion is drawn for PX4 or any flight target.

## Planned content

Problem, test bench and measurement, paired experiment, held-out evaluation, cross-source check, limitations,
reproduction commands, and a table that maps every reported number to its source artifact and the command that
re-checks it.
