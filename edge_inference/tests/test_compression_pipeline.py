"""Synthetic checks only: no experiment runs or held-out dataset access."""
import sys
from pathlib import Path

import numpy as np
import pytest
import onnx
import onnxruntime as ort
import torch
from torch import nn

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

from edge_inference.scripts.compress_pruning import slim
from edge_inference.scripts.quantize_int8 import Reader, quantize
from edge_inference.scripts.eval_compression_variants import as_inputs
from edge_inference.src import offload_sim as sim


def test_calibration_membership_only_from_train():
    pool=[f'train{i}.jpg' for i in range(110)]
    inv={'splits':{'train':{'files':pool},'val':{'files':['v.jpg']},'test':{'files':['t.jpg']}}}
    first=Reader(inv,'images').names
    pool.reverse()
    assert first==Reader(inv,'images').names
    assert len(set(first))==100 and set(first)<=set(pool)


def test_c2f_slim_is_physical_and_trainable():
    from ultralytics.nn.modules import C2f
    net=nn.Module()
    net.model=nn.Sequential(C2f(16,32,n=2,shortcut=True))
    count=lambda: sum(p.numel() for p in net.parameters())
    old=count()
    slim(net)
    y=net.model(torch.ones(2,16,12,12))
    assert y.shape==(2,32,12,12) and count()<old
    assert net.model[0].cv1.conv.out_channels==2*net.model[0].c<32
    y.mean().backward()
    assert all(p.grad is not None for p in net.parameters())


def test_configurable_width_c2f_and_detect(monkeypatch):
    from copy import deepcopy
    from ultralytics.nn.modules import C2f, Detect
    monkeypatch.setattr(Detect, 'legacy', True)  # YOLOv8 detection tower layout
    base = nn.Module()
    base.model = nn.ModuleList([C2f(16, 32, n=2, shortcut=True), Detect(nc=5, ch=(32,))])
    base.model[1].stride.fill_(8)
    counts = []
    for ratio, widths in [(0.5, (16, 32, 16)), (2/3, (24, 44, 20))]:
        net = slim(deepcopy(base), ratio).eval()
        body, head = net.model
        assert tuple(layer.conv.weight.shape[0] for layer in
                     (body.cv1, head.cv2[0][0], head.cv3[0][0])) == widths
        with torch.no_grad():
            decoded, _ = head([body(torch.ones(1, 16, 12, 12))])
        assert decoded.shape == (1, 9, 144) and decoded.isfinite().all()
        counts.append(sum(p.numel() for p in net.parameters()))
    assert counts[0] < counts[1] < sum(p.numel() for p in base.parameters())


@pytest.mark.parametrize('ratio', [0, 1, -0.1, 1.1, float('nan'), float('inf')])
def test_invalid_ratio_rejected_before_pruning(ratio):
    with pytest.raises(ValueError, match='width ratio'):
        slim(nn.Module(), ratio)


def test_static_qdq_roundtrip(tmp_path):
    from onnx import helper as h, TensorProto as t, numpy_helper
    inp=h.make_tensor_value_info('x',t.FLOAT,[1,1,4,4])
    out=h.make_tensor_value_info('y',t.FLOAT,[1,1,4,4])
    conv=h.make_node('Conv',['x','w'],['y'],name='conv')
    weights=numpy_helper.from_array(np.ones((1,1,1,1),np.float32),'w')
    graph=h.make_model(h.make_graph([conv],'synthetic',[inp],[out],[weights]),
                       opset_imports=[h.make_opsetid('',17)],ir_version=8)
    src,dst=tmp_path/'source.onnx',tmp_path/'qdq.onnx'
    onnx.save(graph,src)
    x=np.arange(16,dtype=np.float32).reshape(1,1,4,4)
    class Calibration:
        rows=iter([{'x':x}])
        def get_next(self): return next(self.rows,None)
    counts=quantize(src,dst,Calibration())
    assert counts['QuantizeLinear'] and counts['DequantizeLinear']
    y=ort.InferenceSession(str(dst),providers=['CPUExecutionProvider']).run(None,{'x':x})[0]
    np.testing.assert_allclose(y,x,atol=.1)


def test_record_joins_and_preserves_incomplete_references():
    f=dict(frame_id='f',width=16,height=16,payload_bytes=40)
    t=dict(preprocess=1,inference=2,postprocess=1,total=4,sample_id='cpu4:f')
    b=dict(bbox=[1,1,12,12],class_id='crack',confidence=.7)
    rec=dict(frames=[f],ground_truth={'f':dict(width=16,height=16,boxes=[b],complete=False)},
             edge_predictions={'f':[b]},cloud_predictions={'f':[b]},edge_timings={'f':t},
             cloud_timings={'f':dict(t,sample_id='gpu:f')},provenance={})
    inputs=as_inputs(rec)
    result=sim.simulate(inputs,sim.SimulationConfig(policy='all_edge'))
    assert not result.accuracy.available and result.accuracy.support['crack']==1
    assert result.accuracy.map50 is None
