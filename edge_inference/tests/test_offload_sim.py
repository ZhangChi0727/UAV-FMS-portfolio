import inspect
import json
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.offload_sim import (CGAOPolicy, Detection, EvaluationConfig, FrameContext, FrameTrace,
                            ObservedFrameTrace, OffloadDecision, ReferenceFrame,
                            SimulationConfig, decide, evaluate, main, simulate,
                            sweep, synthetic_traces)


def detection(score=0.8, box=(0, 0, 10, 10), cls='crack'):
    return Detection(box, cls, score)


def test_strategy_band_and_legacy_metrics():
    scores = (.149, .15, .499, .5)
    detections = tuple(detection(score, (i, i, 10, 10)) for i, score in enumerate(scores))
    context = FrameContext('f', detections, 128, 1.)
    decision = CGAOPolicy().decide(context)
    assert decision.offload == decide(detections, policy='cgao')
    assert decision.roi_boxes == (detections[1].bbox, detections[2].bbox)
    traces = synthetic_traces()
    assert simulate(traces, SimulationConfig(policy=CGAOPolicy())) == simulate(traces, SimulationConfig())


def test_injected_strategy_only_sees_immutable_current_observations():
    seen = []
    class AgeGate:
        def decide(self, context):
            seen.append(context)
            return OffloadDecision(context.aoi_ms is not None)

    t = synthetic_traces()
    first, second = t.frames
    t = replace(t, frames=(ObservedFrameTrace(**vars(first), aoi_ms=5., uq_radius=.2), second))
    r = simulate(t, SimulationConfig(policy=AgeGate()))
    assert [row['offload'] for row in r.rows] == [True, False]
    assert [(c.frame_id, c.aoi_ms, c.uq_radius) for c in seen] == [
        (first.frame_id, 5., .2), (second.frame_id, None, None)]
    assert {f.name for f in fields(FrameContext)} == {
        'frame_id','edge_detections','payload_bytes','edge_latency_ms','aoi_ms','uq_radius'}
    with pytest.raises(FrozenInstanceError):
        seen[0].payload_bytes = 0


@pytest.mark.parametrize('scores,expected', [([], False), ([0.149], False),
    ([0.15], True), ([0.499], True), ([0.5], False), ([0.99, 0.2], True)])
def test_decide_boundaries(scores, expected):
    assert decide(tuple(detection(s) for s in scores), policy='cgao') is expected


def test_policy_visibility_and_baselines():
    assert set(inspect.signature(decide).parameters) == {'edge_detections', 'policy', 'tau_low', 'tau'}
    assert decide((), policy='all_cloud')
    assert not decide((detection(0.3),), policy='all_edge')
    with pytest.raises(TypeError):
        decide((), policy='cgao', ground_truth={})


def test_hand_calculated_policies():
    traces = synthetic_traces()  # 1000 + 3000 bytes; edge 10 ms, cloud 2 ms
    cfg = SimulationConfig(bandwidth_mbps=1)
    edge = simulate(traces, replace(cfg, policy='all_edge'))
    assert [r['e2e_ms'] for r in edge.rows] == [10, 10]
    assert [r['energy_mj'] for r in edge.rows] == [100, 100]
    assert edge.summary['offload_ratio'] == 0
    assert edge.summary['bandwidth_saving'] == 1
    cloud = simulate(traces, replace(cfg, policy='all_cloud'))
    assert [r['tx_ms'] for r in cloud.rows] == [8, 24]
    assert [r['edge_ms'] for r in cloud.rows] == [0, 0]
    assert [r['e2e_ms'] for r in cloud.rows] == [30, 46]
    assert [r['energy_mj'] for r in cloud.rows] == [24, 72]
    assert cloud.summary['latency_ms'] == pytest.approx({'mean': 38, 'p95': 45.2, 'p99': 45.84})
    assert cloud.summary['mean_energy_mj'] == 48
    assert cloud.summary['offload_ratio'] == 1
    assert cloud.summary['bandwidth_saving'] == 0
    gated = simulate(traces, cfg)
    assert [r['e2e_ms'] for r in gated.rows] == [40, 10]
    assert [r['energy_mj'] for r in gated.rows] == [124, 100]
    assert gated.summary['latency_ms'] == pytest.approx({'mean': 25, 'p95': 38.5, 'p99': 39.7})
    assert gated.summary['mean_energy_mj'] == 112
    assert gated.summary['offload_ratio'] == 0.5
    assert gated.summary['bandwidth_saving'] == 0.75  # NOT 1-rho
    assert [r['prediction_source'] for r in gated.rows] == ['cloud', 'edge']


def test_roi_only_scales_cgao_tx():
    traces = synthetic_traces()
    cfg = SimulationConfig(bandwidth_mbps=1, alpha_roi=0.5)
    result = simulate(traces, cfg)
    assert result.rows[0]['transmitted_bytes'] == 500
    assert result.rows[0]['e2e_ms'] == 36
    assert result.rows[0]['energy_mj'] == 112
    assert result.summary['bandwidth_saving'] == 0.875
    assert not result.accuracy.available  # no false ROI accuracy claim
    assert result.accuracy.map50 is None
    assert 'ROI' in result.accuracy.reason
    cloud = simulate(traces, replace(cfg, policy='all_cloud'))
    assert cloud.rows[0]['tx_ms'] == 8
    assert cloud.rows[0]['energy_mj'] == 24
    assert cloud.accuracy.available


@pytest.mark.parametrize('field,value', [('bandwidth_mbps', 0), ('bandwidth_mbps', float('nan')),
    ('rtt_ms', -1), ('compute_power_w', float('inf')), ('tx_power_w', -1),
    ('alpha_roi', 0), ('alpha_roi', 1.1), ('tau', 0.96), ('tau_low', 0.5)])
def test_invalid_config(field, value):
    with pytest.raises(ValueError, match=field):
        simulate(synthetic_traces(), replace(SimulationConfig(), **{field: value}))


@pytest.mark.parametrize('field', ['edge_predictions', 'cloud_predictions', 'edge_timings', 'cloud_timings'])
def test_mismatched_frame_sets(field):
    traces = synthetic_traces()
    bad = dict(getattr(traces, field))
    bad['wrong-id'] = bad.pop('s1')
    with pytest.raises(ValueError, match='s1.*wrong-id'):
        simulate(replace(traces, **{field: bad}), SimulationConfig())


def test_duplicate_missing_id_empty_frames():
    traces = synthetic_traces()
    for frames, message in ((traces.frames + (traces.frames[0],), 's0.*duplicate'),
                            ((replace(traces.frames[0], frame_id=''),), 'frame_id'),
                            ((), 'empty trace')):
        with pytest.raises(ValueError, match=message):
            simulate(replace(traces, frames=frames), SimulationConfig())


@pytest.mark.parametrize('field,value', [('payload_bytes', 0), ('payload_bytes', -1),
                                      ('payload_bytes', 2.5), ('width', 0), ('height', True)])
def test_invalid_frame_fields(field, value):
    traces = synthetic_traces()
    bad = replace(traces.frames[0], **{field: value})
    with pytest.raises(ValueError, match=f's0.{field}'):
        simulate(replace(traces, frames=(bad, traces.frames[1])), SimulationConfig())


@pytest.mark.parametrize('box', [(-1, 0, 10, 10), (0, 0, 101, 10), (10, 0, 10, 10),
                               (0, 12, 10, 10), (0, 0, 10, float('nan'))])
def test_invalid_boxes(box):
    traces = synthetic_traces()
    with pytest.raises(ValueError, match='s0.edge_predictions.bbox'):
        simulate(replace(traces, edge_predictions={'s0': (detection(box=box),), 's1': ()}), SimulationConfig())


@pytest.mark.parametrize('score', [-0.1, 1.1, float('inf'), float('nan')])
def test_invalid_scores(score):
    traces = synthetic_traces()
    with pytest.raises(ValueError, match='s0.edge_predictions.confidence'):
        simulate(replace(traces, edge_predictions={'s0': (detection(score),), 's1': ()}), SimulationConfig())


@pytest.mark.parametrize('stage', ['preprocess', 'inference', 'postprocess', 'total'])
@pytest.mark.parametrize('value', [-1, float('nan'), float('inf')])
def test_invalid_timings(stage, value):
    traces = synthetic_traces()
    timings = dict(traces.edge_timings)
    timings['s0'] = replace(timings['s0'], **{stage: value})
    with pytest.raises(ValueError, match=f's0.edge_timings.{stage}'):
        simulate(replace(traces, edge_timings=timings), SimulationConfig())


def test_gate_retention_and_reference_join():
    traces = synthetic_traces()
    with pytest.raises(ValueError, match='gate_retention_floor'):
        simulate(replace(traces, gate_retention_floor=0.25), SimulationConfig())
    with pytest.raises(ValueError, match='references.*s1'):
        simulate(replace(traces, references={'s0': traces.references['s0']}), SimulationConfig())
    refs = dict(traces.references)
    refs['s0'] = replace(refs['s0'], width=99)
    with pytest.raises(ValueError, match='s0.references'):
        simulate(replace(traces, references=refs), SimulationConfig())


@pytest.mark.parametrize('references', [None, {}])
def test_missing_references(references):
    result = simulate(replace(synthetic_traces(), references=references), SimulationConfig())
    assert result.accuracy.available is False
    assert result.accuracy.map50 is None and result.accuracy.map50_95 is None
    assert all(v is None for v in result.accuracy.per_class_recall.values())


def test_perfect_and_zero_support():
    traces = synthetic_traces()
    result = evaluate(traces.cloud_predictions, traces.references)
    assert result.available
    assert result.map50 == result.map50_95 == 1
    assert result.per_class_recall['crack'] == 1
    assert result.per_class_recall['spallation'] == 1
    assert result.per_class_recall['corrosion_stain'] is None
    missing = evaluate({'s0': (), 's1': ()}, traces.references)
    assert missing.map50 == missing.map50_95 == 0
    assert missing.per_class_recall['crack'] == 0


def test_false_positive_ranking_duplicates_and_iou_grid():
    refs = {'f': ReferenceFrame(100, 100, (detection(),))}
    pred = {'f': (detection(0.9, (20, 20, 30, 30)), detection(0.8), detection(0.7))}
    result = evaluate(pred, refs)
    assert result.map50 == result.map50_95 == pytest.approx(0.5)
    assert result.per_class_recall['crack'] == 1
    # IoU exactly 0.5: pass only the first of ten thresholds.
    half = evaluate({'f': (detection(box=(0, 0, 5, 10)),)}, refs)
    assert half.map50 == 1
    assert half.map50_95 == pytest.approx(0.1)
    # One prediction cannot match two annotations.
    two = {'f': ReferenceFrame(100, 100, (detection(), detection()))}
    result = evaluate({'f': (detection(),)}, two)
    assert result.per_class_recall['crack'] == 0.5
    assert result.map50 == pytest.approx(51/101)


def test_coverage_and_evaluator_boundaries():
    pred = {'f': (detection(0.2),)}
    refs = {'f': ReferenceFrame(100, 100, (detection(),))}
    result = evaluate(pred, refs)
    assert result.map50 == 1 and result.per_class_recall['crack'] == 0
    assert evaluate(pred, refs, EvaluationConfig(recall_confidence=0.2)).per_class_recall['crack'] == 1
    for ref in (replace(refs['f'], complete=False), replace(refs['f'], has_ignore_regions=True),
                replace(refs['f'], boxes=())):
        assert not evaluate(pred, {'f': ref}).available
    with pytest.raises(ValueError, match='frame_id mismatch'):
        evaluate({'other': ()}, refs)


def test_sweep_baseline_families_determinism_and_bandwidth():
    traces = synthetic_traces()
    result = sweep(traces)
    assert len(result['cgao']) == 21
    assert set(result['baselines']) == {'all_edge', 'all_cloud'}
    assert len(result['baselines']['all_cloud']) == 3
    assert [r['rows'][0]['e2e_ms'] for r in result['baselines']['all_cloud']] == [30, 23.6, 22.4]
    for tau_index in range(7):
        assert result['cgao'][tau_index]['accuracy'] == result['cgao'][tau_index+7]['accuracy']
    assert json.dumps(result, sort_keys=True, allow_nan=False) == json.dumps(sweep(traces), sort_keys=True, allow_nan=False)
    reordered = replace(traces, frames=tuple(reversed(traces.frames)))
    assert simulate(traces, SimulationConfig()).rows == simulate(reordered, SimulationConfig()).rows


def test_cli_json_and_labels(tmp_path, monkeypatch):
    import src.offload_sim as module
    # Default destination must be independent of the working directory.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, '__file__', str(tmp_path / 'edge_inference/src/offload_sim.py'))
    main(['--synthetic'])
    output = tmp_path / 'edge_inference/docs/offload-sim-synthetic.json'
    text = output.read_text(encoding='utf-8')
    result = json.loads(text, parse_constant=lambda token: pytest.fail(token))
    assert result['trace_kind'] == 'synthetic_not_measured'
    assert result['host_type'] == 'development-host'
    assert result['output_kind'] == 'analytical_simulation'
    assert len(result['cgao']) == 21
    assert len(result['cgao'][0]['metadata']['input_sha256']) == 64
    with pytest.raises(SystemExit):
        main([])


def test_decisions_do_not_depend_on_cloud_or_labels():
    traces = synthetic_traces()
    first = simulate(traces, SimulationConfig())
    changed = replace(traces, cloud_predictions={'s0': (), 's1': ()}, references=None,
                      cloud_timings={fid: replace(t, total=100) for fid, t in traces.cloud_timings.items()})
    second = simulate(changed, SimulationConfig())
    assert [r['offload'] for r in first.rows] == [r['offload'] for r in second.rows]


def test_matching_is_class_specific_and_ties_are_stable():
    refs = {'f': ReferenceFrame(100, 100, (detection(),))}
    wrong_class = evaluate({'f': (detection(cls='spallation'),)}, refs)
    assert wrong_class.map50 == 0
    false_first = {'f': (detection(0.8, (20, 20, 30, 30)), detection(0.8))}
    assert evaluate(false_first, refs).map50 == 0.5
    assert evaluate(false_first, refs) == evaluate(false_first, refs)


def test_unknown_class_bad_sample_and_metadata():
    traces = synthetic_traces()
    with pytest.raises(ValueError, match='s0.*class_id'):
        simulate(replace(traces, edge_predictions={'s0': (detection(cls='unknown'),), 's1': ()}), SimulationConfig())
    with pytest.raises(ValueError, match='s0.*sample_id'):
        simulate(replace(traces, edge_timings={**traces.edge_timings,
                 's0': replace(traces.edge_timings['s0'], sample_id='')}), SimulationConfig())
    with pytest.raises(ValueError, match='provenance'):
        simulate(replace(traces, provenance={'bad': float('nan')}), SimulationConfig())
