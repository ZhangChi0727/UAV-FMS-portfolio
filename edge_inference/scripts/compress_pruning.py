"""Physically slim YOLOv8 C2f and Detect internal widths; no test input to recovery."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import shutil

import torch
from torch import nn
import yaml

from edge_inference.scripts.prepare_codebrim import EDGE, digest, write_json

DATA = EDGE / 'data/codebrim_yolo'
RUN = EDGE / 'runs/yolov8n_pruned'
BEST = EDGE / 'runs/yolov8n_fp32_baseline/weights/best.pt'
MANIFEST = '7321eaef3d7cd3526e7489e4c3872554f6f8741a2030e5ff45dcb5bf461adf84'
BASE_PT = 'ffd8228000e0c5ca385b58389d212aba7a19a5b14a6a4f4e3b36209005e6f255'
BASE_ONNX = '9ee091bd2a70a5b99ea3f93712d9f6774f02c65d1576f0e444d9b7f31d8fbc3e'
SCRATCH = EDGE.parent / 'build/day23-recovery-data'
DEFAULT_WIDTH_RATIO = 2 / 3


def manifest():
    p = DATA / 'split_manifest.json'
    if digest(p) != MANIFEST:
        raise ValueError('split manifest changed')
    return json.loads(p.read_text())


def checked_ratio(value):
    ratio = float(value)
    if not 0 < ratio < 1:
        raise ValueError('width ratio must be in (0, 1)')
    return ratio


def keep(scores, width_ratio: float = DEFAULT_WIDTH_RATIO):
    n = min(len(scores), max(4, 4 * round(len(scores) * checked_ratio(width_ratio) / 4)))
    return scores.argsort(descending=True, stable=True)[:n].sort().values


def l1(layer):
    # [TRACEABILITY] Spec/Req: EDG-REQ-0036; Literature Basis: structured filter L1 ranking.
    # Vault-ID: none (implementation-only script)
    # sum absolute weights per output channel; local slicing is not a learned importance proof.
    return layer.conv.weight.detach().abs().sum((1, 2, 3))


@torch.no_grad()
def slice_conv(layer, inputs=None, outputs=None):
    conv = layer if isinstance(layer, nn.Conv2d) else layer.conv
    if conv.groups != 1:
        raise ValueError('unsupported grouped convolution')
    w = conv.weight
    if inputs is not None:
        w = w[:, inputs]
    if outputs is not None:
        w = w[outputs]
        if conv.bias is not None:
            conv.bias = nn.Parameter(conv.bias[outputs].clone())
        if hasattr(layer, 'bn'):
            bn = layer.bn
            for k in ('weight', 'bias'):
                setattr(bn, k, nn.Parameter(getattr(bn, k)[outputs].clone()))
            for k in ('running_mean', 'running_var'):
                setattr(bn, k, getattr(bn, k)[outputs].clone())
            bn.num_features = len(outputs)
    conv.weight = nn.Parameter(w.contiguous().clone())
    conv.out_channels, conv.in_channels = w.shape[:2]


def slim(model, width_ratio: float = DEFAULT_WIDTH_RATIO):
    width_ratio = checked_ratio(width_ratio)
    from ultralytics.nn.modules import C2f, Detect
    for block in model.model:
        if isinstance(block, C2f):
            c = block.c
            scores = l1(block.cv1).reshape(2, c).sum(0)
            for bottleneck in block.m:
                scores += l1(bottleneck.cv2)
            idx = keep(scores, width_ratio)
            slice_conv(block.cv1, outputs=torch.cat((idx, idx+c)))
            for b in block.m:
                inner = keep(l1(b.cv1), width_ratio)
                slice_conv(b.cv1, idx, inner)
                slice_conv(b.cv2, inner, idx)
            slice_conv(block.cv2, torch.cat([idx+j*c for j in range(2+len(block.m))]))
            block.c = len(idx)
        elif isinstance(block, Detect):
            for tower in [*block.cv2, *block.cv3]:
                a, b = keep(l1(tower[0]), width_ratio), keep(l1(tower[1]), width_ratio)
                slice_conv(tower[0], outputs=a)
                slice_conv(tower[1], a, b)
                slice_conv(tower[2], b)
    return model


def costs(model):
    from ultralytics.utils.torch_utils import get_flops
    return dict(parameters=sum(p.numel() for p in model.parameters()), gflops=get_flops(model, 640))


def train(width_ratio: float = DEFAULT_WIDTH_RATIO):
    width_ratio = checked_ratio(width_ratio)
    from ultralytics import YOLO
    from ultralytics.models.yolo.detect import DetectionTrainer
    if RUN.exists() or digest(BEST) != BASE_PT:
        raise ValueError('run exists or baseline changed')
    m = manifest()
    SCRATCH.mkdir(parents=True, exist_ok=False)
    for s in ('train','val'):
        for name in m['splits'][s]['files']:
            for kind, fname, key in [('images',name,'image_sha256'),('labels',Path(name).stem+'.txt','label_sha256')]:
                source = DATA/kind/s/fname
                target = SCRATCH/kind/s/fname
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source,target)
                if digest(target) != m['images'][name][key]:
                    raise ValueError(source)
    cfg = SCRATCH/'data.yaml'
    cfg.write_text(yaml.safe_dump(dict(path=SCRATCH.as_posix(),train='images/train',val='images/val',names=m['classes'])))
    model = YOLO(BEST).model.float()
    before = costs(model)
    slim(model, width_ratio)
    after = costs(model)
    if not all(0 < after[k] < before[k] for k in before):
        raise RuntimeError('physical reduction not verified')
    print(before,after,flush=True)
    tr = DetectionTrainer(overrides=dict(model=str(BEST), data=str(cfg), project=str(RUN.parent),
        name=RUN.name, epochs=20, imgsz=640, batch=16, seed=42, workers=4, amp=False,
        device=0, deterministic=True, plots=False, optimizer='AdamW', lr0=.001))
    tr.model = model
    write_json(RUN/'pruning.json',dict(before=before,after=after,source_sha256=BASE_PT,split_sha256=MANIFEST,
        width_ratio=width_ratio, width_rule='retained width rounded to nearest multiple of four, '
        'at least four and at most the original width; best validation epoch'))
    tr.train()


def export():
    from ultralytics import YOLO
    import onnx
    import onnxslim
    target = EDGE/'weights/yolov8n_pruned_fp32.onnx'
    if target.exists():
        raise FileExistsError(target)
    p = RUN/'weights/best.pt'
    net = YOLO(p)
    record = json.loads((RUN/'pruning.json').read_text())
    if costs(net.model)['parameters'] != record['after']['parameters']:
        raise ValueError('checkpoint lost pruned architecture')
    # Explicit simplification: an unsuccessful simplifier must fail the command.
    path = net.export(format='onnx',imgsz=640,opset=17,batch=1,dynamic=False,simplify=False,half=False,device=0,nms=False)
    graph = onnxslim.slim(str(path))
    onnx.checker.check_model(graph)
    def shapes(path):
        g = onnx.load(path)
        dims = {i.name: tuple(i.dims) for i in g.graph.initializer}
        return Counter(dims[n.input[1]] for n in g.graph.node if n.op_type=='Conv')
    onnx.save(graph,target)
    if shapes(target) == shapes(EDGE/'weights/yolov8n_fp32_baseline.onnx'):
        raise ValueError('unchanged ONNX Conv dimensions')
    write_json(RUN/'export.json', dict(model_sha256=digest(target),best_sha256=digest(p),**record))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    stages = parser.add_subparsers(dest='stage', required=True)
    stages.add_parser('train').add_argument('--width-ratio', type=checked_ratio, default=DEFAULT_WIDTH_RATIO,
        help='fraction of internal channels to retain before rounding (default: 2/3)')
    stages.add_parser('export')
    args = parser.parse_args()
    os.environ['YOLO_CONFIG_DIR'] = str(EDGE.parent/'build/ultralytics-settings')
    os.environ['YOLO_AUTOINSTALL'] = 'false'
    torch.backends.cuda.matmul.allow_tf32 = torch.backends.cudnn.allow_tf32 = False
    if args.stage == 'train':
        train(args.width_ratio)
    else:
        export()
