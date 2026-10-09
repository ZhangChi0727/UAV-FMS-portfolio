# Literature review protocol

## Status and ownership

- Protocol version: `0.2-draft`
- Review owner: `Chi Zhang`
- Date approved: `TBD`
- Last amended: `2026-10-09`
- Scope: UAV flight-management-system state estimation, fault detection,
  fault-tolerant control, closed-loop resilience, and verification/safety evidence
- Reporting approach: PRISMA 2020-informed, adapted for an engineering thesis

This protocol must be approved before formal searches begin. Exploratory searches
used to refine vocabulary must be labelled `pilot` in `search_log.csv`.

## Review objectives

1. Characterize methods used for UAV INS/GNSS estimation and navigation during
   degraded or unavailable GNSS.
2. Characterize model-based and data-driven sensor/actuator fault detection and
   isolation approaches relevant to UAV flight management.
3. Compare learning-assisted Kalman filtering and fault-tolerant-control approaches
   by assumptions, inputs, fault models, validation level, and reported metrics.
4. Identify evidence about closed-loop behavior when estimation, detection, and
   control interact.
5. Determine which proposed thesis claims are directly supported, contradicted, or
   still require evidence.

These objectives guide evidence collection; they are not novelty claims.

## Modular research amendment

The project now supports independent research packages (see ../research/README.md).
The July pilot corpus remains historical discovery evidence. Extend future searches
to real-time control implementation, delay/jitter, scenario-based verification,
test oracles, simulation fidelity and SIL/HIL evidence transfer. Run and log each
package's searches separately; a shared platform does not imply one thesis or paper.
No new searches or full-text findings are asserted by this scope amendment.
Date limits and formal search approval remain unresolved from the initial protocol.

## Sources

Formal searches should cover, subject to institutional access:

- IEEE Xplore
- Scopus or Web of Science
- Engineering Village / Compendex, if available
- Consensus for supplementary semantic discovery
- OpenAlex for supplementary citation-network discovery
- Crossref and publisher pages for DOI/metadata validation

Google Scholar may be used for supplementary discovery but should not be the sole
source for a reproducible search.

## Search concepts

Build database-specific queries from these concept groups. Record the exact final
syntax in `search_log.csv`; do not treat this table as an executed search.

| Concept | Candidate terms |
|---|---|
| Platform | UAV, unmanned aerial vehicle, drone, multirotor, quadrotor |
| Estimation | INS/GNSS, inertial navigation, sensor fusion, EKF, UKF, Kalman filter |
| Degradation | GNSS-denied, GPS outage, spoofing, sensor fault, actuator fault |
| Detection | fault detection, fault isolation, anomaly detection, FDI, TCN |
| Resilience | fault tolerant control, reconfiguration, mode management, resilient navigation |
| Evidence | simulation, SIL, HIL, flight test, Monte Carlo, verification, safety |

Candidate Boolean structure:

```text
(UAV OR "unmanned aerial vehicle" OR drone OR multirotor)
AND
(navigation OR estimation OR control OR "fault detection")
AND
("GNSS denied" OR "GPS outage" OR spoofing OR fault OR anomaly OR resilient)
```

Adapt field codes, phrase syntax, wildcards, and controlled vocabulary per database.

## Eligibility criteria

### Include

- Peer-reviewed journal or conference papers, and high-quality review papers.
- Studies addressing at least one review objective.
- UAV-specific evidence, or transferable methods with a clearly relevant vehicle,
  sensor, estimator, detector, controller, or verification context.
- Full text available in a language the reviewer can assess.
- Sufficient method and evaluation detail to extract at least the core evidence
  fields.

### Exclude

- Editorials, posters, patents, marketing material, tutorials without original
  evidence, and non-scholarly web pages.
- Pure path-planning or perception work with no relevant estimation, FDI,
  fault-tolerant control, resilience, or verification contribution.
- Duplicate reports of the same study when a more complete version is available;
  link companion reports instead.
- Studies for which relevance cannot be established after full-text review.

### Date and language limits

- Publication date range: `TBD after pilot searches`
- Language: `English` unless the protocol is explicitly amended

Any added restriction requires a rationale and an amendment entry.

## Record management and deduplication

1. Import authoritative metadata into Zotero and preserve DOI, URL, abstract, and
   source database.
2. Export candidate metadata to a working CSV and run
   `notebooks/deduplicate.ipynb`.
3. Treat normalized DOI equality as the strongest automatic duplicate signal.
4. Treat normalized title equality as a candidate duplicate requiring manual
   confirmation, especially for conference/journal extensions.
5. Preserve one canonical record and populate `duplicate_of` for removed records.
6. Never delete a screening decision merely because the record is a duplicate.

## Screening

- Stage 1: title and abstract.
- Stage 2: full text.
- Allowed decisions: `include`, `exclude`, `maybe`, or `not_screened`.
- Every exclusion must use a controlled reason from the evidence workbook.
- Resolve `maybe` records before synthesis.
- A second reviewer or an explicit re-check should be used for ambiguous and
  claim-critical studies where feasible.
- Record the reviewer and decision date.

## Metadata and DOI validation

- Normalize a DOI by removing URL/prefix forms, trimming whitespace, and lowercasing.
- Validate the DOI against Crossref and the publisher landing page.
- Resolve title, author, year, venue, and work-type discrepancies in Zotero.
- Record unresolved discrepancies in `screening.csv` notes.
- Do not infer a DOI from title similarity alone.

## Full-text evidence extraction

Use one row per study in the `Studies` sheet and one row per distinct finding in
`Evidence Extraction`. Capture:

- stable study/citation identifier;
- full citation and DOI;
- research objective and claimed contribution;
- platform, sensors, dataset, and operating scenario;
- estimation, detection, and control methods;
- fault type, magnitude, onset, duration, and assumptions;
- baselines and ablations;
- metrics, numeric result, unit, uncertainty, and sample/trial count;
- validation level (theoretical, simulation, SIL, HIL, or flight test);
- source locator (page, section, figure, or table);
- concise paraphrase, limitations, and applicability to this project.

Never invent a missing value. Use `not_reported`, explain the gap, and distinguish a
reported result from the reviewer's calculation.

## Quality and relevance assessment

Apply the documented questions in the `Quality Appraisal` sheet. The score is a
navigation aid, not a substitute for judgment. Consider:

- clarity of objective and method;
- reproducibility of data, configuration, and evaluation;
- appropriateness of comparator and metrics;
- disclosure of uncertainty, sample size, and limitations;
- validation realism;
- direct relevance to the claim or design decision being assessed.

Do not exclude a study solely because it reports a negative or non-significant
result.

## Synthesis

- Produce descriptive counts by topic, method, fault, platform, and validation level.
- Use structured narrative synthesis when configurations and metrics are not
  comparable.
- Pool numeric results only when populations, scenarios, metrics, and uncertainty are
  sufficiently compatible and the analysis method is approved in an amendment.
- Keep reported values separate from reviewer-derived values.
- Cite the retained study identifier for every comparison and proposed claim.

## Claim governance

The `claim_ledger.md` is the gate for novelty language:

1. Write a narrowly scoped candidate claim.
2. State what evidence would falsify or narrow it.
3. Link supporting, contradicting, and adjacent studies.
4. Record unresolved search gaps.
5. Assign `proposed`, `supported`, `narrowed`, `rejected`, or `needs_search`.

No claim becomes thesis-ready until its scope, evidence, counter-evidence, and
limitations have been reviewed.

## PRISMA-informed reporting

Retain counts for:

- records identified by each database and supplementary method;
- records removed before screening, including DOI/title duplicates;
- records screened at title/abstract stage;
- records excluded at title/abstract stage;
- full texts sought and not retrieved;
- full texts assessed and excluded, with reasons;
- studies included in qualitative and any quantitative synthesis.

Use `notebooks/search_audit.ipynb` to flag missing log fields and reconcile counts.
Generate any flow figure from checked counts and retain it under `figures/`.

## Protocol amendments

| Date | Version | Section | Change | Rationale | Impact on completed work | Author |
|---|---|---|---|---|---|---|
| TBD | 0.1 | Initial draft | Protocol created | Establish reproducible workflow | No searches executed | Chi Zhang |
| 2026-10-09 | 0.2-draft | Research scope | Add independent timing and verification research packages | Align modular platform | Preserve July pilot records; no retrospective reclassification | Chi Zhang |
