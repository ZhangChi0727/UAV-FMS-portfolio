# G1.5-B joint-baseline candidate review

Status: **candidate pending PA review and D2**. This review does not approve,
freeze, satisfy, implement, or verify any B0 product requirement.

## Review object

- D1-approved method: JSON-led normative requirement source, SysML textual
  model, independent verification catalogue, deterministic Markdown/StrictDoc
  projections.
- Candidate inventory: 30 requirements, 26 stable model identities and 29
  verification specifications. Every verification result remains `not_run` and
  null.
- Frozen numeric authority remains
  `05_integration/b0/configs/b0_g0_contract.v2.json`; values are referenced, not
  copied into a second numerical authority.
- Legacy `CTL-REQ-001/002` remain byte-preserved historical requirements and are
  `not_applicable` only to current B0 under the retained G0 decision.

## Purpose and coverage review

| Engineering question | Candidate requirements | Model responsibility | Planned verification | Review conclusion |
|---|---|---|---|---|
| Bounded purpose, replay and exclusions | 0001–0003, 0030 | system, scenario, execution | scope, replay and exclusion inspections | covered; no flight/navigation expansion |
| Shared conventions | 0004 | all message boundaries | convention analysis | covered by G0 references |
| Plant and quaternion propagation | 0005–0006 | plant | independent equations/tests | covered; future execution is G1 evidence |
| Paired torque and actuation | 0007–0009 | controller/actuator interfaces | clamp, response and timestamp tests | covered; controller is unique limiter |
| IMU and truth boundary | 0010–0011 | plant/IMU | gyro/specific-force tests | covered; truth never enters estimator/controller |
| Estimation and limitations | 0012–0015, 0029 | estimator | propagation/fusion/limitation/invalid tests | covered; absolute yaw is excluded |
| Cascaded control | 0016–0019 | controller | sign, saturation, anti-windup and rejection tests | covered; no performance result claimed |
| Reset and multi-rate execution | 0020–0021 | execution and stateful components | replay and integer-tick scheduling tests | covered |
| Scenario/evaluator/evidence | 0022–0025 | scenario/evaluator/evidence | catalogue, independence, provenance, mutation checks | covered as planned provisions |
| Language, clean reproduction, legacy | 0026–0028 | system/release roles | inspection/demonstration | covered; future work remains explicit |

## Quality and ambiguity review

- Each candidate has one normative `shall` statement, rationale, source,
  applicability, responsibility, model allocation, acceptance condition and at
  least one bidirectionally checked verification allocation.
- Stable identities are separately registered; the next ordinal is monotonic.
  Substantive obligation changes require a new identity and `supersedes` link.
- The model declares paired command fields and both interface directions. The
  parser accepts the exact source. Because sysmlpy 0.33.2 omits `expose` from its
  retained AST, a version-bound manual review is tied to the model SHA-256;
  changing the bytes invalidates that review.
- Verification specifications distinguish component from integration/release
  stages and include preconditions, inputs, initial conditions, steps,
  independent oracle, decision rule, invalid handling, evidence type and owner.
- No critical TBD remains in the interpretation needed by G1.5-C. Future
  implementations and executions are intentionally not present.

## Risks and residual limits

| Risk/assumption | Basis and impact | Owner / treatment | Closure condition |
|---|---|---|---|
| sysmlpy retains incomplete view semantics | observed parser boundary; a false automated expose claim would be misleading | systems engineering; hash-bound manual review | supported AST or repeated manual review on changed source |
| Static direction checks do not prove runtime timing | model is descriptive, not executable | G2/G3 owners; execute paired-command and schedule provisions | retained test trace satisfies planned oracle |
| Requirement wording may change after D2 feedback | all entries are candidates | PA/user; changes create new S/M candidate | exact S and M receive D2 approval |
| Existing G1 evidence predates this allocation | link alone cannot establish satisfaction | verification reviewer; perform applicability/difference review in C | evidence provenance and scope accepted without invented result |

## Automated and manual claims

The formal checker proves structural consistency only: schema, identities,
references, allocation symmetry, selected model interface/truth invariants,
planned-result truthfulness, source presence, projection drift and hash-bound
manual-review freshness. Engineering sufficiency, oracle independence and
product behaviour remain human/future-execution judgments.
