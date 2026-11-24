"""Detector adapters. ONNX output is explicitly limited to raw YOLOv8 detection heads."""
import time
import numpy as np


def letterbox_tensor(frame, ih, iw):
    """Shared inference/calibration transform from decoded BGR pixels."""
    import cv2
    h, w = frame.shape[:2]
    scale = min(iw / w, ih / h)
    nw, nh = round(w * scale), round(h * scale)
    resized = cv2.resize(frame, (nw, nh))
    left, top = (iw - nw) // 2, (ih - nh) // 2
    canvas = np.full((ih, iw, 3), 114, dtype=np.uint8)
    canvas[top:top+nh, left:left+nw] = resized
    tensor = np.ascontiguousarray(canvas[:, :, ::-1].transpose(2, 0, 1)[None], dtype=np.float32) / 255.0
    return tensor, scale, left, top


class EdgeDefectDetector:
    def __init__(self, model, provider='cpu', threads=4, backend='onnx', confidence=0.25, iou=0.45):
        if provider not in ('cpu', 'cuda') or threads < 1:
            raise ValueError('invalid provider or thread count')
        self.provider, self.backend = provider, backend
        self.confidence, self.iou = confidence, iou
        if backend == 'onnx':
            import onnxruntime as ort
            if provider == 'cuda':
                # Windows CUDA/cuDNN DLLs can be supplied by the PyTorch wheel.
                ort.preload_dlls()
            name = 'CUDAExecutionProvider' if provider == 'cuda' else 'CPUExecutionProvider'
            if name not in ort.get_available_providers():
                raise RuntimeError(f'{name} unavailable; refusing silent fallback')
            options = ort.SessionOptions()
            options.intra_op_num_threads = threads
            if provider == 'cpu':
                options.inter_op_num_threads = 1
            # CUDA EP defaults to reduced-mantissa TF32 on Ampere+. Keep the
            # development FP32 baseline explicit (ORT >= 1.18).
            providers = [(name, {'use_tf32': 0})] if provider == 'cuda' else [name]
            self.session = ort.InferenceSession(str(model), sess_options=options, providers=providers)
            if self.session.get_providers()[0] != name:
                raise RuntimeError('requested provider was not selected')
            self.input = self.session.get_inputs()[0]
            if len(self.session.get_inputs()) != 1 or self.input.type != 'tensor(float)':
                raise ValueError('only single-input float32 ONNX models supported')
        elif backend == 'ultralytics':
            from ultralytics import YOLO
            self.model = YOLO(str(model))
        else:
            raise ValueError('unknown backend')

    def infer(self, frame: np.ndarray) -> dict:
        if not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError('expected HWC uint8 BGR frame')
        t0 = time.perf_counter_ns()
        if self.backend == 'ultralytics':
            # Ultralytics owns the three stages; its reported speed values are used.
            result = self.model.predict(frame, device=0 if self.provider == 'cuda' else 'cpu', verbose=False)[0]
            boxes = result.boxes
            detections = [] if boxes is None else [{'xyxy': b.xyxy[0].tolist(), 'confidence': float(b.conf[0]), 'class_id': int(b.cls[0])} for b in boxes]
            speed = result.speed
            times = {k: float(speed[k]) for k in ('preprocess', 'inference', 'postprocess')}
            times['total'] = (time.perf_counter_ns() - t0) / 1e6
            return {'detections': detections, 'timings_ms': times}
        import cv2
        h, w = frame.shape[:2]
        shape = self.input.shape
        if len(shape) != 4 or not isinstance(shape[2], int) or not isinstance(shape[3], int):
            raise ValueError('ONNX input must have fixed NCHW height and width')
        ih, iw = shape[2:4]
        tensor, scale, left, top = letterbox_tensor(frame, ih, iw)
        t1 = time.perf_counter_ns()
        outputs = self.session.run(None, {self.input.name: tensor})
        t2 = time.perf_counter_ns()
        if len(outputs) != 1 or outputs[0].ndim != 3 or outputs[0].shape[0] != 1:
            raise ValueError('expected one raw YOLOv8 output [1, 4+classes, anchors]')
        raw = outputs[0][0]
        if raw.shape[0] < 5 or raw.shape[0] >= raw.shape[1]:
            raise ValueError('unsupported detection head layout')
        rows = raw.T
        cls = np.argmax(rows[:, 4:], axis=1)
        scores = rows[np.arange(len(rows)), 4 + cls]
        keep = np.isfinite(rows).all(axis=1) & (scores >= self.confidence)
        rows, scores, cls = rows[keep], scores[keep], cls[keep]
        boxes = []
        for row in rows:
            x, y, bw, bh = row[:4]
            x1, y1 = np.clip((x-bw/2-left)/scale, 0, w), np.clip((y-bh/2-top)/scale, 0, h)
            x2, y2 = np.clip((x+bw/2-left)/scale, 0, w), np.clip((y+bh/2-top)/scale, 0, h)
            boxes.append([float(x1), float(y1), float(max(0, x2-x1)), float(max(0, y2-y1))])
        detections = []
        for c in np.unique(cls):
            indices = np.flatnonzero(cls == c)
            # Scores already passed the inclusive >= confidence filter. Avoid
            # OpenCV's second, strict > score threshold dropping equality at .15.
            selected = cv2.dnn.NMSBoxes([boxes[i] for i in indices], [float(scores[i]) for i in indices], 0.0, self.iou)
            for j in np.asarray(selected).reshape(-1):
                i = indices[j]; x, y, bw, bh = boxes[i]
                if bw > 0 and bh > 0:
                    detections.append({'xyxy': [x, y, x+bw, y+bh], 'confidence': float(scores[i]), 'class_id': int(c)})
        t3 = time.perf_counter_ns()
        times = {'preprocess': (t1-t0)/1e6, 'inference': (t2-t1)/1e6, 'postprocess': (t3-t2)/1e6, 'total': (t3-t0)/1e6}
        return {'detections': detections, 'timings_ms': times}
