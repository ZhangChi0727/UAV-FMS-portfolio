"""Replay immutable Day 1–3 JSONs; no model session, dataset or inference."""
import json
from pathlib import Path

import numpy as np

from edge_inference.scripts.eval_compression_variants import as_inputs
from edge_inference.scripts.prepare_codebrim import EDGE, digest
from edge_inference.src import offload_sim as sim

DOC = EDGE / 'docs'
OUTPUT = DOC / 'offload-sim-codebrim-results.json'
DISCLOSURE = ('Annotation-relative descriptive metrics on the 104 admitted test images '
              '(864 XML reference rows); not exhaustive whole-image ground-truth coverage (`complete=false`).')
TRACES = {
    'fp32_baseline': '50a4bea5bcd3187f08bdb8ad00d85b32484c121b71c9ea48f0449acbbe9420d1',
    'pruned_fp32': 'e059a388a2a3f714c966e9c4694bafd39e49ad3b362d84730488bdb7a3a3b7de',
    'int8': 'd7857b70faefbbb2e3f6538d0e44c853483e2505dd9d754ca9897000c8f62456',
    'pruned_int8': 'ed3e3eee5dfc77c497eae8386bfbf0fac85f21be452757c403d2ca92fbf02fe8',
}
CLOUD_HASH = 'b5737af3a6ddbafa9e8815e20d096e1dc46d712834fae1b4ec660d1b3d0a68a9'


def checked(path, expected):
    if digest(path) != expected:
        raise ValueError(f'trace identity mismatch: {path}')
    return json.loads(path.read_text(encoding='utf-8'))


def descriptive(pred, refs):
    """Greedy v1 matches against supplied rows only. Never change coverage flags."""
    cfg = sim.EvaluationConfig()
    strict = sim.evaluate(pred, refs, cfg)  # validates IDs, boxes, scores and labels
    by_class = {}
    for cls, n in strict.support.items():
        if not n:
            by_class[cls] = dict(support=0, ap50=None, ap50_95=None, recall=None)
            continue
        aps = []
        for threshold in strict.protocol['iou_grid']:
            hits = sim._matches(pred, refs, cls, threshold)
            tp = np.cumsum(hits)
            precision = tp / np.arange(1, len(tp)+1)
            aps.append(float(np.mean([np.max(precision[tp/n >= r], initial=0.)
                                      for r in np.linspace(0, 1, 101)])))
        recall = sim._matches(pred, refs, cls, cfg.recall_iou, cfg.recall_confidence).sum()/n
        by_class[cls] = dict(support=n, ap50=aps[0], ap50_95=float(np.mean(aps)), recall=float(recall))
    supported = [v for v in by_class.values() if v['support']]
    return dict(disclosure=DISCLOSURE, protocol=strict.protocol, per_class=by_class,
                **{k:float(np.mean([v[f] for v in supported])) if supported else None
                   for k,f in [('map50','ap50'),('map50_95','ap50_95')]})


def points(grid):
    return [grid['baselines']['all_edge'], *grid['baselines']['all_cloud'], *grid['cgao']]


def main():
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    cloud = checked(DOC/'fp32-test-trace.json', CLOUD_HASH)
    result = dict(host='development-host', kind='analytical_simulation', disclosure=DISCLOSURE,
                  trace_hashes=TRACES, cloud_hash=CLOUD_HASH, primary={}, roi={})
    for variant, sha in TRACES.items():
        record = checked(DOC/f'trace-{variant}-cpu4.json', sha)
        for k in ('frames','cloud_timings','cloud_predictions','ground_truth'):
            if record[k] != cloud[k]:
                raise ValueError(f'{variant}: cached {k} differs from Day 1')
        inp = as_inputs(record)
        if (len(inp.frames)!=104 or sum(len(v.boxes) for v in inp.references.values())!=864
                or any(v.complete or v.has_ignore_regions for v in inp.references.values())):
            raise ValueError('unexpected reference inventory')
        grid = sim.sweep(inp)
        cache = {}
        for p in points(grid):
            # Bandwidth changes time, not prediction identity. Reuse only exact
            # frame/source selections from the same verified input trace.
            key = tuple((r['frame_id'],r['prediction_source']) for r in p['rows'])
            if key not in cache:
                pred = {fid:(inp.cloud_predictions if source=='cloud' else inp.edge_predictions)[fid]
                        for fid,source in key}
                cache[key] = descriptive(pred, inp.references)
            p['annotation_relative'] = cache[key]
        result['primary'][variant] = grid
        if variant.startswith('pruned'):
            roi = sim.sweep(inp, sim.SimulationConfig(alpha_roi=.35))
            for full, small in zip(grid['cgao'],roi['cgao'],strict=True):
                if small['accuracy']['available'] or not all(
                    a['offload']==b['offload'] and np.isclose(.35*a['transmitted_bytes'],b['transmitted_bytes'])
                    for a,b in zip(full['rows'],small['rows'],strict=True)):
                    raise ValueError('ROI sensitivity changed decisions or accuracy')
            result['roi'][variant] = roi
        print(variant, 'completed', flush=True)
    with OUTPUT.open('x',encoding='utf-8') as out:
        json.dump(result,out,separators=(',',':'),allow_nan=False)
    print(OUTPUT.name,digest(OUTPUT))


if __name__ == '__main__':
    main()
