"""Independent-frame analytical replay; no model, dataset or network execution.

Evaluator v1: class-wise, score-descending greedy one-to-one IoU matching;
ties use sorted frame ID then prediction index (GT ties use annotation index).
AP is the mean interpolated precision at 101 recall points, without maxDets,
area ranges, crowd or ignore-region support. This is not the COCO API evaluator.
Defaults are synthetic demonstration settings, not test-tuned operating points.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field, replace
import hashlib
import json
import math
from numbers import Real
from pathlib import Path
from typing import Literal, Mapping, Sequence

import numpy as np

Policy = Literal['all_edge', 'all_cloud', 'cgao']
CLASSES = ('crack', 'spallation', 'efflorescence', 'exposed_bar', 'corrosion_stain')
CAVEATS = (
    'Analytical simulation, not hardware, network, battery or flight measurements.',
    'Independent frames: no queuing, overlap, loss, retries, deadlines or control dynamics.',
    'Energy excludes idle/RX, encoding, camera, avionics, propulsion and cloud wall-power.',
    'CPU/GPU profiles are development-host references, not onboard/cloud-service measurements.',
)


@dataclass(frozen=True)
class Detection:
    bbox: tuple[float, float, float, float]
    class_id: str
    confidence: float


@dataclass(frozen=True)
class FrameTrace:
    frame_id: str
    width: int
    height: int
    payload_bytes: int


@dataclass(frozen=True)
class StageTiming:
    preprocess: float
    inference: float
    postprocess: float
    total: float
    sample_id: str


@dataclass(frozen=True)
class ReferenceFrame:
    width: int
    height: int
    boxes: tuple[Detection, ...]  # confidence validated but not used as a GT weight
    complete: bool = True
    has_ignore_regions: bool = False


@dataclass(frozen=True)
class EvaluationConfig:
    classes: tuple[str, ...] = CLASSES
    recall_confidence: float = 0.25
    recall_iou: float = 0.5
    version: str = 'greedy-101point-v1'


@dataclass(frozen=True)
class TraceInputs:
    frames: Sequence[FrameTrace]
    edge_predictions: Mapping[str, Sequence[Detection]]
    cloud_predictions: Mapping[str, Sequence[Detection]]
    edge_timings: Mapping[str, StageTiming]
    cloud_timings: Mapping[str, StageTiming]
    references: Mapping[str, ReferenceFrame] | None = None
    provenance: dict = field(default_factory=dict)
    trace_kind: Literal['synthetic_not_measured', 'development_host_trace'] = 'synthetic_not_measured'
    gate_retention_floor: float = 0.15


@dataclass(frozen=True)
class SimulationConfig:
    policy: Policy = 'cgao'
    # [TRACEABILITY] Spec/Req: offload_sim_spec §3–5; EDG-REQ-0038 (stage timings only).
    # Literature Basis: resource-scheduling context; Vault-ID: lit-20261124-uav-edge-resource-survey.
    # Analytical/Engineering Scope: bandwidth, RTT and power are scenario inputs, not measured constants.
    bandwidth_mbps: float = 5.0
    rtt_ms: float = 20.0
    tau_low: float = 0.15
    tau: float = 0.5
    alpha_roi: float = 1.0
    compute_power_w: float = 10.0
    tx_power_w: float = 3.0
    evaluation: EvaluationConfig = field(default_factory=EvaluationConfig)


@dataclass(frozen=True)
class AccuracyResult:
    available: bool
    map50: float | None
    map50_95: float | None
    per_class_recall: dict[str, float | None]
    support: dict[str, int]
    reason: str | None
    protocol: dict


@dataclass(frozen=True)
class SimulationResult:
    config: dict
    rows: list[dict]
    summary: dict
    accuracy: AccuracyResult
    metadata: dict


def _number(value, name, low=0.0, high=math.inf):
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{name}: expected finite number in [{low}, {high}]')


def _positive_int(value, name):
    if type(value) is not int or value <= 0:
        raise ValueError(f'{name}: expected positive integer')


def _ids(mapping, expected, name):
    if set(mapping) != expected:
        raise ValueError(f'{name} frame_id mismatch: missing={sorted(expected-set(mapping), key=str)}, '
                         f'extra={sorted(set(mapping)-expected, key=str)}')


def _detection(d, width, height, classes, name):
    if (not isinstance(d, Detection) or not isinstance(d.bbox, (tuple, list))
            or len(d.bbox) != 4):
        raise ValueError(f'{name}: invalid Detection/bbox')
    for value in d.bbox:
        _number(value, f'{name}.bbox')
    x1, y1, x2, y2 = d.bbox
    if not (x1 < x2 <= width and y1 < y2 <= height):
        raise ValueError(f'{name}.bbox: outside frame or degenerate box')
    if d.class_id not in classes:
        raise ValueError(f'{name}.class_id: unknown class {d.class_id!r}')
    _number(d.confidence, f'{name}.confidence', high=1)


def _evaluation_config(config):
    if (not config.classes or any(not isinstance(c, str) or not c for c in config.classes)
            or len(set(config.classes)) != len(config.classes)):
        raise ValueError('evaluation.classes: unique nonempty names required')
    _number(config.recall_confidence, 'recall_confidence', high=1)
    _number(config.recall_iou, 'recall_iou', high=1)
    if config.version != 'greedy-101point-v1':
        raise ValueError('unsupported evaluator version')


def decide(edge_detections: Sequence[Detection], *, policy: Policy,
           tau_low: float = 0.15, tau: float = 0.5) -> bool:
    """No references, cloud predictions or future timings are accepted here."""
    if policy not in ('all_edge', 'all_cloud', 'cgao'):
        raise ValueError('policy: unknown policy')
    _number(tau_low, 'tau_low', high=1)
    _number(tau, 'tau', low=0.25, high=0.95)
    if tau_low >= tau:
        raise ValueError('tau_low must be less than tau')
    for d in edge_detections:
        if not isinstance(d, Detection):
            raise ValueError('edge_detections: expected Detection')
        _number(d.confidence, 'edge_detections.confidence', high=1)
    if policy != 'cgao':
        return policy == 'all_cloud'
    # [TRACEABILITY] Spec/Req: offload_sim_spec §3.2; Literature Basis: confidence-gated scheduling.
    # Vault-ID: concept-20261124-cgao-model; Analytical/Engineering Scope: any retained score
    # in the half-open interval triggers uplink; no future cloud output or label is visible.
    return any(tau_low <= d.confidence < tau for d in edge_detections)


def _validate(traces, config):
    _evaluation_config(config.evaluation)
    decide((), policy=config.policy, tau_low=config.tau_low, tau=config.tau)
    for key in ('bandwidth_mbps', 'rtt_ms', 'compute_power_w', 'tx_power_w'):
        _number(getattr(config, key), key)
    if config.bandwidth_mbps == 0:
        raise ValueError('bandwidth_mbps must be positive')
    _number(config.alpha_roi, 'alpha_roi', high=1)
    if config.alpha_roi == 0:
        raise ValueError('alpha_roi must be positive')
    _number(traces.gate_retention_floor, 'gate_retention_floor', high=1)
    if config.policy == 'cgao' and traces.gate_retention_floor > config.tau_low:
        raise ValueError('gate_retention_floor exceeds tau_low; missing gate candidates')
    if traces.trace_kind not in ('synthetic_not_measured', 'development_host_trace'):
        raise ValueError('trace_kind: unsupported provenance label')
    if not traces.frames:
        raise ValueError('frames: empty trace')
    frames = {}
    for f in traces.frames:
        if not isinstance(f, FrameTrace):
            raise ValueError('frames.frame_id: expected FrameTrace')
        if not isinstance(f.frame_id, str) or not f.frame_id.strip():
            raise ValueError('frame_id: missing/nonempty string required')
        if f.frame_id in frames:
            raise ValueError(f'frame_id {f.frame_id}: duplicate')
        for key in ('width', 'height', 'payload_bytes'):
            _positive_int(getattr(f, key), f'{f.frame_id}.{key}')
        frames[f.frame_id] = f
    # [TRACEABILITY] Spec/Req: offload_sim_spec §2; Literature Basis: latency-aware perception.
    # Vault-ID: lit-20261124-perception-control-latency; Analytical/Engineering Scope:
    # frame IDs bind observations, never infer a missing timing or payload.
    for name in ('edge_predictions', 'cloud_predictions', 'edge_timings', 'cloud_timings'):
        _ids(getattr(traces, name), set(frames), name)
    for fid, f in frames.items():
        for name in ('edge_predictions', 'cloud_predictions'):
            for d in getattr(traces, name)[fid]:
                _detection(d, f.width, f.height, config.evaluation.classes, f'{fid}.{name}')
        for name in ('edge_timings', 'cloud_timings'):
            t = getattr(traces, name)[fid]
            if not isinstance(t, StageTiming) or not isinstance(t.sample_id, str) or not t.sample_id:
                raise ValueError(f'{fid}.{name}.sample_id: required')
            for key in ('preprocess', 'inference', 'postprocess', 'total'):
                _number(getattr(t, key), f'{fid}.{name}.{key}')
    if traces.references:
        _ids(traces.references, set(frames), 'references')
        for fid, ref in traces.references.items():
            if not isinstance(ref, ReferenceFrame):
                raise ValueError(f'{fid}.references: expected ReferenceFrame')
            if (ref.width, ref.height) != (frames[fid].width, frames[fid].height):
                raise ValueError(f'{fid}.references: dimensions mismatch')
    # Reject metadata that cannot be retained in strict JSON.
    try:
        json.dumps(traces.provenance, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise ValueError('provenance: must be finite JSON metadata') from exc
    return frames


def _iou(a, b):
    overlap = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    area_a = (a[2]-a[0])*(a[3]-a[1])
    area_b = (b[2]-b[0])*(b[3]-b[1])
    return overlap / (area_a + area_b - overlap)


def _matches(predictions, references, cls, threshold, score_floor=0.0):
    ranked = sorted(((-d.confidence, fid, index, d) for fid in sorted(predictions)
                     for index, d in enumerate(predictions[fid])
                     if d.class_id == cls and d.confidence >= score_floor), key=lambda x: x[:3])
    used = {fid: set() for fid in references}
    hits = []
    for _, fid, _, detection in ranked:
        candidates = [(index, _iou(detection.bbox, gt.bbox))
                      for index, gt in enumerate(references[fid].boxes)
                      if gt.class_id == cls and index not in used[fid]]
        best = max(candidates, key=lambda item: (item[1], -item[0]), default=None)
        hit = best is not None and best[1] >= threshold
        if hit:
            used[fid].add(best[0])
        hits.append(int(hit))
    return np.asarray(hits, dtype=float)


def evaluate(predictions: Mapping[str, Sequence[Detection]],
             references: Mapping[str, ReferenceFrame] | None,
             config: EvaluationConfig = EvaluationConfig()) -> AccuracyResult:
    _evaluation_config(config)
    protocol = {**asdict(config), 'ap': '101-point interpolated precision; all retained scores',
                'matching': 'greedy score-descending; frame_id/index tie-break; one-to-one',
                'iou_grid': [round(0.5 + i*0.05, 2) for i in range(10)],
                'limitations': 'No crowd/ignore/area/maxDets support; not COCO API parity.'}
    support = dict.fromkeys(config.classes, 0)
    recalls = dict.fromkeys(config.classes, None)
    def unavailable(reason):
        return AccuracyResult(False, None, None, recalls, support, reason, protocol)
    if not references:
        return unavailable('missing ground truth; latency-only evaluation')
    _ids(predictions, set(references), 'predictions/references')
    for fid, ref in references.items():
        if not isinstance(fid, str) or not fid.strip():
            raise ValueError('references.frame_id: missing ID')
        if not isinstance(ref, ReferenceFrame):
            raise ValueError(f'{fid}.references: expected ReferenceFrame')
        _positive_int(ref.width, f'{fid}.width')
        _positive_int(ref.height, f'{fid}.height')
        if type(ref.complete) is not bool or type(ref.has_ignore_regions) is not bool:
            raise ValueError(f'{fid}.references: coverage flags must be boolean')
        for d in ref.boxes:
            _detection(d, ref.width, ref.height, config.classes, f'{fid}.ground_truth')
            support[d.class_id] += 1
        for d in predictions[fid]:
            _detection(d, ref.width, ref.height, config.classes, f'{fid}.predictions')
    # [TRACEABILITY] Spec/Req: offload_sim_spec §6; Literature Basis: offline detection matching.
    # Vault-ID: concept-20261124-cgao-model; Analytical/Engineering Scope: strict accuracy
    # requires coverage, unlike a descriptive comparison to supplied rows.
    if any(not r.complete or r.has_ignore_regions for r in references.values()):
        return unavailable('incomplete labels or unsupported ignore regions; accuracy unavailable')
    if not any(support.values()):
        return unavailable('no ground-truth class support')
    ap_by_class = []
    for cls, count in support.items():
        if not count:
            continue
        aps = []
        for threshold in protocol['iou_grid']:
            hits = _matches(predictions, references, cls, threshold)
            tp = np.cumsum(hits)
            recall = tp/count
            precision = tp/np.arange(1, len(hits)+1)
            aps.append(float(np.mean([np.max(precision[recall >= r], initial=0.0)
                                      for r in np.linspace(0, 1, 101)])))
        ap_by_class.append(aps)
        recalls[cls] = float(_matches(predictions, references, cls, config.recall_iou,
                                     config.recall_confidence).sum()/count)
    return AccuracyResult(True, float(np.mean([a[0] for a in ap_by_class])),
                          float(np.mean(ap_by_class)), recalls, support, None, protocol)


def simulate(traces: TraceInputs, config: SimulationConfig) -> SimulationResult:
    frames = _validate(traces, config)
    rows, selected = [], {}
    for fid in sorted(frames):
        f = frames[fid]
        edge, cloud = traces.edge_timings[fid], traces.cloud_timings[fid]
        offload = decide(traces.edge_predictions[fid], policy=config.policy,
                         tau_low=config.tau_low, tau=config.tau)
        edge_ms = 0.0 if config.policy == 'all_cloud' else edge.total
        scale = config.alpha_roi if config.policy == 'cgao' else 1.0
        sent = f.payload_bytes*scale if offload else 0.0
        # [TRACEABILITY] Spec/Req: offload_sim_spec §4–5; Literature Basis: resource and latency accounting.
        # Vault-ID: lit-20261124-uav-edge-resource-survey; Analytical/Engineering Scope:
        # Bytes to bits, Mbps to ms; W times ms gives mJ. No measured network or battery.
        tx_ms = 8*sent/(1000*config.bandwidth_mbps)
        rtt_ms, cloud_ms = (config.rtt_ms, cloud.total) if offload else (0.0, 0.0)
        latency = edge_ms + tx_ms + rtt_ms + cloud_ms
        energy = config.compute_power_w*edge_ms + config.tx_power_w*tx_ms
        _number(latency, f'{fid}.e2e_ms')
        _number(energy, f'{fid}.energy_mj')
        selected[fid] = traces.cloud_predictions[fid] if offload else traces.edge_predictions[fid]
        rows.append(dict(frame_id=fid, offload=offload, payload_bytes=f.payload_bytes,
                         transmitted_bytes=sent, edge_sample_id=edge.sample_id,
                         cloud_sample_id=cloud.sample_id, edge_profile_total_ms=edge.total,
                         cloud_profile_total_ms=cloud.total, edge_ms=edge_ms, tx_ms=tx_ms,
                         rtt_ms=rtt_ms, cloud_ms=cloud_ms, e2e_ms=latency, energy_mj=energy,
                         prediction_source='cloud' if offload else 'edge',
                         selected_predictions=[asdict(d) for d in selected[fid]]))
    times = [r['e2e_ms'] for r in rows]
    total_bytes = sum(f.payload_bytes for f in frames.values())
    sent_bytes = math.fsum(r['transmitted_bytes'] for r in rows)
    count = sum(r['offload'] for r in rows)
    summary = dict(n=len(rows), offload_count=count, offload_ratio=count/len(rows),
                   input_bytes=total_bytes, transmitted_bytes=sent_bytes,
                   bandwidth_saving=1-sent_bytes/total_bytes,
                   latency_ms={'mean': float(np.mean(times)),
                               'p95': float(np.percentile(times, 95, method='linear')),
                               'p99': float(np.percentile(times, 99, method='linear'))},
                   mean_energy_mj=math.fsum(r['energy_mj']/len(rows) for r in rows))
    accuracy = evaluate(selected, traces.references, config.evaluation)
    caveats = list(CAVEATS)
    if config.policy == 'cgao' and config.alpha_roi != 1:
        accuracy = replace(accuracy, available=False, map50=None, map50_95=None,
                           per_class_recall=dict.fromkeys(config.evaluation.classes, None),
                           reason='ROI byte-scaling only; no matching ROI prediction/timing traces')
        caveats.append('ROI is communication sensitivity only; full-frame predictions retained, not ROI accuracy.')
    fingerprint = hashlib.sha256(json.dumps(asdict(traces), sort_keys=True,
                                             allow_nan=False).encode()).hexdigest()
    return SimulationResult(asdict(config), rows, summary, accuracy,
                            dict(host_type='development-host', trace_kind=traces.trace_kind,
                                 output_kind='analytical_simulation', input_sha256=fingerprint,
                                 units={'latency': 'ms', 'energy': 'mJ', 'payload': 'Bytes',
                                        'bandwidth': 'Mbps', 'power': 'W', 'ratios_and_accuracy': 'fraction'},
                                 provenance=traces.provenance, caveats=caveats))


def sweep(traces: TraceInputs, config: SimulationConfig = SimulationConfig()) -> dict:
    """21 CGAO points + two baseline families; cloud retains all three bandwidths."""
    bandwidths = (1.0, 5.0, 20.0)
    taus = (0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85)
    base = config  # Default RTT is 20 ms; preserve explicit caller settings.
    return {'baselines': {
        'all_edge': asdict(simulate(traces, replace(base, policy='all_edge', bandwidth_mbps=1.0))),
        'all_cloud': [asdict(simulate(traces, replace(base, policy='all_cloud', bandwidth_mbps=b)))
                      for b in bandwidths]},
        'cgao': [asdict(simulate(traces, replace(base, policy='cgao', bandwidth_mbps=b, tau=t)))
                 for b in bandwidths for t in taus],
        'grid_note': '21 CGAO points; 2 baseline families (1 edge + 3 bandwidth-dependent cloud runs).'}


def synthetic_traces() -> TraceInputs:
    frames = (FrameTrace('s0', 100, 100, 1000), FrameTrace('s1', 100, 100, 3000))
    edge = {'s0': (Detection((0, 0, 10, 10), 'crack', 0.3),), 's1': ()}
    cloud = {'s0': (Detection((0, 0, 10, 10), 'crack', 0.9),),
             's1': (Detection((20, 20, 30, 30), 'spallation', 0.9),)}
    return TraceInputs(frames, edge, cloud,
                       {f.frame_id: StageTiming(1, 8, 1, 10, f'edge-{f.frame_id}') for f in frames},
                       {f.frame_id: StageTiming(0.5, 1, 0.5, 2, f'cloud-{f.frame_id}') for f in frames},
                       {fid: ReferenceFrame(100, 100, boxes) for fid, boxes in cloud.items()},
                       provenance={'source': 'literal synthetic fixture v1; no model or dataset',
                                   'edge_profile': 'analytical CPU-4 reference, not measured',
                                   'cloud_profile': 'analytical RTX4060 reference, not measured',
                                   'timing_mapping': 'fixed sample IDs; no random draws',
                                   'split': 'synthetic demonstration only'})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--synthetic', action='store_true')
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] /
                        'docs/offload-sim-synthetic.json')
    parser.add_argument('--alpha-roi', type=float, default=1.0)
    args = parser.parse_args(argv)
    if not args.synthetic:
        parser.error('only --synthetic is supported; no dataset access')
    result = sweep(synthetic_traces(), SimulationConfig(alpha_roi=args.alpha_roi))
    result.update(host_type='development-host', trace_kind='synthetic_not_measured',
                  output_kind='analytical_simulation')
    encoded = json.dumps(result, indent=2, allow_nan=False) + '\n'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded, encoding='utf-8')
    print(f'Wrote {args.output}; synthetic_not_measured; development-host; analytical_simulation')


if __name__ == '__main__':
    main()
