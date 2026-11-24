"""Static QDQ Conv PTQ with fixed MinMax calibration; only training files are read."""
import argparse
from collections import Counter
import json
import random

import cv2
import onnx
from onnxruntime.quantization import (CalibrationDataReader, CalibrationMethod, QuantFormat,
                                      QuantType, quantize_static)

from edge_inference.scripts.compress_pruning import DATA, RUN, BASE_ONNX, manifest
from edge_inference.scripts.prepare_codebrim import EDGE, digest, write_json
from edge_inference.src.detector import letterbox_tensor


class Reader(CalibrationDataReader):
    def __init__(self, inventory, key):
        self.names = random.Random(42).sample(sorted(inventory['splits']['train']['files']),100)
        self.i, self.key, self.inventory = 0, key, inventory

    def get_next(self):
        if self.i == len(self.names):
            return None
        name = self.names[self.i]
        row = self.inventory['images'][name]
        p = DATA/'images/train'/name
        if row['split'] != 'train' or digest(p) != row['image_sha256']:
            raise ValueError(name)
        self.i += 1
        return {self.key: letterbox_tensor(cv2.imread(str(p)),640,640)[0]}


def quantize(src, dst, reader):
    if dst.exists():
        raise FileExistsError(dst)
    quantize_static(str(src), str(dst), reader, quant_format=QuantFormat.QDQ,
                    activation_type=QuantType.QUInt8, weight_type=QuantType.QInt8,
                    calibrate_method=CalibrationMethod.MinMax, per_channel=True,
                    op_types_to_quantize=['Conv'], calibration_providers=['CPUExecutionProvider'])
    graph = onnx.load(dst)
    onnx.checker.check_model(graph)
    counts = Counter(n.op_type for n in graph.graph.node)
    if not counts['QuantizeLinear'] or not counts['DequantizeLinear'] or not any(
        i.data_type == onnx.TensorProto.INT8 for i in graph.graph.initializer):
        raise ValueError('missing static INT8 QDQ weights')
    return dict(counts)


def main(pruned):
    src = EDGE/'weights'/('yolov8n_pruned_fp32.onnx' if pruned else 'yolov8n_fp32_baseline.onnx')
    expected = json.loads((RUN/'export.json').read_text())['model_sha256'] if pruned else BASE_ONNX
    if digest(src) != expected:
        raise ValueError('source changed')
    dst = src.with_name('yolov8n_pruned_int8.onnx' if pruned else 'yolov8n_int8.onnx')
    reader = Reader(manifest(),onnx.load(src).graph.input[0].name)
    counts = quantize(src,dst,reader)
    if reader.i != 100:
        raise ValueError('calibration count')
    write_json(dst.with_suffix('.json'),dict(source_sha256=expected,model_sha256=digest(dst),
        train_files=reader.names,seed=42,calibration='MinMax QUInt8/QInt8 Conv only; per-channel weights',
        op_counts=counts))
    print(dst,digest(dst),flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--pruned',action='store_true')
    main(p.parse_args().pruned)
