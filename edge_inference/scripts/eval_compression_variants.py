"""Freeze all variants before any test inference; join the existing GPU trace offline."""
import argparse
from dataclasses import asdict
import json
import platform
import sys
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

from edge_inference.scripts.prepare_codebrim import CLASSES, EDGE, digest, write_json
from edge_inference.src import offload_sim as sim
from edge_inference.src.benchmark import run
from edge_inference.src.detector import EdgeDefectDetector, letterbox_tensor

DATA = EDGE/'data/codebrim_yolo'
DOC = EDGE/'docs'
FREEZE = EDGE/'runs/yolov8n_pruned/variants-freeze.json'
MODELS = dict(fp32_baseline='yolov8n_fp32_baseline',pruned_fp32='yolov8n_pruned_fp32',
              int8='yolov8n_int8',pruned_int8='yolov8n_pruned_int8')
CLOUD = DOC/'fp32-test-trace.json'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def freeze():
    if FREEZE.exists():
        raise FileExistsError(FREEZE)
    from edge_inference.scripts.compress_pruning import BASE_ONNX, MANIFEST, RUN
    if digest(DATA/'split_manifest.json') != MANIFEST or digest(CLOUD) != 'b5737af3a6ddbafa9e8815e20d096e1dc46d712834fae1b4ec660d1b3d0a68a9':
        raise ValueError('Day 1 data changed')
    hashes = {v:digest(EDGE/'weights'/(name+'.onnx')) for v,name in MODELS.items()}
    if hashes['fp32_baseline'] != BASE_ONNX or hashes['pruned_fp32'] != read(RUN/'export.json')['model_sha256']:
        raise ValueError('FP32 source changed')
    lists = []
    for variant, source in [('int8','fp32_baseline'),('pruned_int8','pruned_fp32')]:
        ptq = read(EDGE/'weights'/(MODELS[variant]+'.json'))
        if ptq['source_sha256'] != hashes[source] or ptq['model_sha256'] != hashes[variant]:
            raise ValueError('PTQ source changed')
        lists.append(ptq['train_files'])
    if lists[0] != lists[1] or len(set(lists[0])) != 100 or not set(lists[0]) <= set(read(DATA/'split_manifest.json')['splits']['train']['files']):
        raise ValueError('calibration mismatch')
    # Diagnostic only: compare pre-NMS head outputs on four fixed validation
    # frames, never use test results or this diagnostic to tune calibration.
    inv=read(DATA/'split_manifest.json')
    diagnostic={}
    for parent,child in [('fp32_baseline','int8'),('pruned_fp32','pruned_int8')]:
        pair=[EdgeDefectDetector(EDGE/'weights'/(MODELS[v]+'.onnx'),provider='cpu',threads=4)
              for v in (parent,child)]
        stats=[]
        for name in sorted(inv['splits']['val']['files'])[:4]:
            path=DATA/'images/val'/name
            if digest(path)!=inv['images'][name]['image_sha256']:
                raise ValueError(name)
            x=letterbox_tensor(cv2.imread(str(path)),640,640)[0]
            a,b=[d.session.run(None,{d.input.name:x})[0] for d in pair]
            if a.shape!=b.shape or a.shape!=(1,9,8400) or not np.isfinite([a,b]).all():
                raise ValueError('invalid validation head outputs')
            diff=np.abs(a-b)
            stats.append(dict(frame=name,box_component_mae_input_pixels=float(diff[:,:4].mean()),
                              class_score_mae=float(diff[:,4:].mean()),max_class_score_delta=float(diff[:,4:].max())))
        diagnostic[child]=stats
    write_json(FREEZE,dict(models=hashes,cloud=digest(CLOUD),manifest=MANIFEST,validation_qdq_diagnostic=diagnostic,
        costs=read(RUN/'pruning.json'),conf=.15,iou=.45,calibration='Conv QDQ U8/S8 per-channel MinMax',
        decoder=digest(EDGE/'src/detector.py'),evaluator=digest(EDGE/'src/offload_sim.py')))


def as_inputs(record):
    def dets(items,gt=False):
        return tuple(sim.Detection(tuple(b['bbox']),b['class_id'],1. if gt else b['confidence']) for b in items)
    refs = {k:sim.ReferenceFrame(v['width'],v['height'],dets(v['boxes'],True),v['complete'])
            for k,v in record['ground_truth'].items()}
    return sim.TraceInputs(frames=[sim.FrameTrace(**{k:f[k] for k in ('frame_id','width','height','payload_bytes')}) for f in record['frames']],
        edge_predictions={k:dets(v) for k,v in record['edge_predictions'].items()},
        cloud_predictions={k:dets(v) for k,v in record['cloud_predictions'].items()},
        edge_timings={k:sim.StageTiming(**v) for k,v in record['edge_timings'].items()},
        cloud_timings={k:sim.StageTiming(**v) for k,v in record['cloud_timings'].items()},
        references=refs,provenance=record['provenance'],trace_kind='development_host_trace')


def measured(variant,stage):
    f = read(FREEZE)
    model = EDGE/'weights'/(MODELS[variant]+'.onnx')
    for path,key in [(DATA/'split_manifest.json','manifest'),(CLOUD,'cloud'),
                     (EDGE/'src/detector.py','decoder'),(EDGE/'src/offload_sim.py','evaluator')]:
        if digest(path) != f[key]:
            raise ValueError(path)
    if digest(model) != f['models'][variant]:
        raise ValueError(model)
    out = DOC/f'{stage}-{variant}-cpu4.json'
    if out.exists():
        raise FileExistsError(out)
    inv = read(DATA/'split_manifest.json')
    def image(name,s):
        p = DATA/'images'/s/name
        if digest(p) != inv['images'][name]['image_sha256']:
            raise ValueError(p)
        return cv2.imread(str(p))
    cv2.setNumThreads(4)
    detector = EdgeDefectDetector(model, provider='cpu',threads=4,confidence=f['conf'],iou=f['iou'])
    warm = image('image_0000021.jpg','val')
    meta = dict(variant=variant,host_type='development-host',host=platform.node(),cpu=platform.processor(),
        model_sha256=digest(model),model_size_MB=model.stat().st_size/1e6,freeze_sha256=digest(FREEZE),
        split_manifest_sha256=f['manifest'],cloud_trace_sha256=f['cloud'],source_compute=f['costs']['after' if 'pruned' in variant else 'before'],
        backend='ONNX Runtime '+ort.__version__,provider=detector.session.get_providers(),intra_threads=4,
        inter_threads=1,opencv_threads=4,warmup=20,warmup_frame='image_0000021.jpg',command=sys.argv,
        imgsz=640,confidence=.15,iou=.45,precision='static QDQ INT8 Conv' if 'int8' in variant else 'FP32',
        coordinates='zero-based half-open original-image pixels',class_map=CLASSES)
    if stage=='profile':
        write_json(out, {**meta,**run(detector,warm,20,100)})
        return
    c = read(CLOUD)
    frames = {row['frame_id']:row for row in c['frames']}
    names = inv['splits']['test']['files']
    if len(names)!=104 or len(c['frames'])!=104 or {Path(n).stem for n in names}!=set(frames):
        raise ValueError('test frame mismatch')
    for _ in range(20):
        detector.infer(warm)
    preds,times = {},{}
    # Exclusive durable marker before the first test inference. Partial attempts
    # cannot be silently restarted, even when the process fails before final JSON.
    marker = FREEZE.parent/(variant+'-test-started.jsonl')
    with marker.open('x',encoding='utf-8') as journal:
        print(json.dumps(meta),file=journal,flush=True)
        for name in names:
            k=Path(name).stem
            img=image(name,'test')
            row=frames[k]
            if (img.shape[:2] != (row['height'],row['width']) or row['payload_bytes']!=(DATA/'images/test'/name).stat().st_size
                    or row['image_sha256']!=inv['images'][name]['image_sha256']):
                raise ValueError('frame metadata mismatch')
            result=detector.infer(img)
            preds[k]=[dict(class_id=CLASSES[b['class_id']],bbox=b['xyxy'],confidence=b['confidence']) for b in result['detections']]
            times[k]=dict(**result['timings_ms'],sample_id=f'{variant}:cpu4:{k}')
            print(json.dumps([k,preds[k],times[k]],allow_nan=False),file=journal,flush=True)
    record=dict(trace_kind='development_host_trace',gate_retention_floor=.15,provenance=meta,
        edge_profile=meta,cloud_profile=c['provenance'],frames=c['frames'],edge_predictions=preds,edge_timings=times,
        cloud_predictions=c['cloud_predictions'],cloud_timings=c['cloud_timings'],ground_truth=c['ground_truth'])
    inputs=as_inputs(record)
    sim._validate(inputs,sim.SimulationConfig())
    record['accuracy']=asdict(sim.evaluate(inputs.edge_predictions,inputs.references))
    write_json(out,record)


def panels():
    left,right=[read(DOC/f'trace-{v}-cpu4.json') for v in ('fp32_baseline','pruned_int8')]
    dest=EDGE/'runs/compression_qualitative'
    dest.mkdir(exist_ok=False)
    chosen=set()
    for cls in ('crack','spallation'):
        # Highest number of annotated regions, then ID. No ranking by model success.
        ranked=sorted(left['ground_truth'], key=lambda k:(-sum(b['class_id']==cls for b in left['ground_truth'][k]['boxes']),k))
        for k in [key for key in ranked if key not in chosen][:2]:
            chosen.add(k)
            img=cv2.imread(str(DATA/'images/test'/(k+'.jpg')))
            cols=[]
            for title,boxes in [('XML',left['ground_truth'][k]['boxes']),('FP32',left['edge_predictions'][k]),('Pruned+INT8',right['edge_predictions'][k])]:
                s=min(550/img.shape[0],550/img.shape[1])
                panel=cv2.resize(img,None,fx=s,fy=s)
                for b in boxes:
                    if b['class_id']!=cls: continue
                    x,y,u,v=[round(z*s) for z in b['bbox']]
                    cv2.rectangle(panel,(x,y),(u,v),(40,230,250),2)
                panel=cv2.copyMakeBorder(panel,32,0,0,0,cv2.BORDER_CONSTANT)
                cv2.putText(panel,f'{k}: {title} / {cls}',(4,21),0,.47,(255,255,255),1)
                cols.append(panel)
            if not cv2.imwrite(str(dest/f'{cls}-{k}.jpg'),np.hstack(cols)):
                raise OSError(dest)


def summarize():
    """Audit cached artifacts and print report rows without invoking a model."""
    f = read(FREEZE)
    for variant, name in MODELS.items():
        model = EDGE/'weights'/(name+'.onnx')
        pf = DOC/f'profile-{variant}-cpu4.json'
        tf = DOC/f'trace-{variant}-cpu4.json'
        p, t = read(pf), read(tf)
        identity = digest(model)
        if not (identity == f['models'][variant] == p['model_sha256'] == t['provenance']['model_sha256']):
            raise ValueError('artifact identity mismatch')
        if p['freeze_sha256'] != digest(FREEZE) or t['provenance']['freeze_sha256'] != digest(FREEZE):
            raise ValueError('freeze mismatch')
        if len(p['samples_ms']) != 100 or len(t['frames']) != 104:
            raise ValueError('incorrect observation count')
        for stage in ('preprocess','inference','postprocess','total'):
            raw = np.asarray([row[stage] for row in p['samples_ms']])
            actual = [raw.mean(), *np.percentile(raw,[95,99])]
            reported = [p['summary_ms'][stage][k] for k in ('mean','p95','p99')]
            np.testing.assert_allclose(actual,reported,rtol=1e-12,atol=1e-12)
        journal = FREEZE.parent/(variant+'-test-started.jsonl')
        lines = journal.read_text().splitlines()
        if len(lines) != 105 or json.loads(lines[0]) != t['provenance']:
            raise ValueError('test journal mismatch')
        seen = set()
        for line in lines[1:]:
            key, boxes, timing = json.loads(line)
            if key in seen or boxes != t['edge_predictions'][key] or timing != t['edge_timings'][key]:
                raise ValueError('frame journal mismatch')
            seen.add(key)
        if sum(t['accuracy']['support'].values()) != 864:
            raise ValueError('incorrect reference support')
        print(json.dumps(dict(variant=variant,MB=model.stat().st_size/1e6,ms=p['summary_ms'],
            RSS_MB=p['sampled_peak_rss_bytes']/1e6,outputs=sum(len(v) for v in t['edge_predictions'].values()),
            accuracy_available=t['accuracy']['available'],onnx=identity,profile=digest(pf),trace=digest(tf))))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('stage',choices=['freeze','profile','trace','panels','summarize'])
    p.add_argument('variant',nargs='?',choices=MODELS)
    a=p.parse_args()
    if a.stage=='freeze': freeze()
    elif a.stage=='panels': panels()
    elif a.stage=='summarize': summarize()
    elif a.variant: measured(a.variant,a.stage)
    else: p.error('profile and trace require variant')
