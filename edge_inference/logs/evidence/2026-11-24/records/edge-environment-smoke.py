"""Local environment check only; no dataset or trained model."""
import sys
import torch
import cv2
import onnx
import onnxruntime as ort
import ultralytics
import numpy as np

print('Python:', sys.version)
for module in (torch, cv2, onnx, ort, ultralytics):
    print(module.__name__, module.__version__)
print('torch.version.cuda:', torch.version.cuda)
print('torch.cuda.is_available():', torch.cuda.is_available())
print('onnxruntime.get_available_providers():', ort.get_available_providers())
assert torch.cuda.is_available()
print('CUDA tensor sum:', torch.ones(4, device='cuda').sum().item())
ort.preload_dlls()
from onnx import helper, TensorProto
graph = helper.make_graph([helper.make_node('Add', ['x', 'x'], ['y'])], 'smoke',
    [helper.make_tensor_value_info('x', TensorProto.FLOAT, [4])],
    [helper.make_tensor_value_info('y', TensorProto.FLOAT, [4])])
model = helper.make_model(graph, opset_imports=[helper.make_opsetid('', 17)], ir_version=9)
session = ort.InferenceSession(model.SerializeToString(), providers=['CUDAExecutionProvider'])
assert session.get_providers()[0] == 'CUDAExecutionProvider'
np.testing.assert_array_equal(session.run(None, {'x': np.ones(4, dtype=np.float32)})[0], np.full(4, 2, dtype=np.float32))
print('ORT CUDA session arithmetic smoke: PASS')
