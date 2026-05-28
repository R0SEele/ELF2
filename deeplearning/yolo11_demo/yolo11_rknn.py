import cv2
import numpy as np


DEFAULT_IMG_SIZE = 640


def load_labels(path, class_count=None):
    if not path:
        return None

    labels = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            label = line.strip()
            if label and not label.startswith("#"):
                labels.append(label)

    if class_count is not None and len(labels) != class_count:
        raise ValueError(
            "labels count ({}) does not match model classes ({})".format(
                len(labels), class_count
            )
        )
    return labels


def make_default_labels(class_count):
    return ["class_{}".format(i) for i in range(class_count)]


def letterbox(image, new_shape=(DEFAULT_IMG_SIZE, DEFAULT_IMG_SIZE), color=(0, 0, 0)):
    shape = image.shape[:2]
    if isinstance(new_shape, int):
        new_shape = (new_shape, new_shape)

    ratio = min(new_shape[0] / shape[0], new_shape[1] / shape[1])
    new_unpad = (int(round(shape[1] * ratio)), int(round(shape[0] * ratio)))
    dw = new_shape[1] - new_unpad[0]
    dh = new_shape[0] - new_unpad[1]
    dw /= 2
    dh /= 2

    if shape[::-1] != new_unpad:
        image = cv2.resize(image, new_unpad, interpolation=cv2.INTER_LINEAR)

    top = int(round(dh - 0.1))
    bottom = int(round(dh + 0.1))
    left = int(round(dw - 0.1))
    right = int(round(dw + 0.1))
    image = cv2.copyMakeBorder(
        image,
        top,
        bottom,
        left,
        right,
        cv2.BORDER_CONSTANT,
        value=color,
    )
    return image, ratio, (left, top)


def xywh_to_xyxy(boxes):
    output = np.empty_like(boxes)
    half_w = boxes[:, 2] / 2
    half_h = boxes[:, 3] / 2
    output[:, 0] = boxes[:, 0] - half_w
    output[:, 1] = boxes[:, 1] - half_h
    output[:, 2] = boxes[:, 0] + half_w
    output[:, 3] = boxes[:, 1] + half_h
    return output


def scale_boxes(boxes, ratio, padding, image_shape):
    boxes[:, [0, 2]] -= padding[0]
    boxes[:, [1, 3]] -= padding[1]
    boxes[:, :4] /= ratio

    h, w = image_shape[:2]
    boxes[:, [0, 2]] = boxes[:, [0, 2]].clip(0, w - 1)
    boxes[:, [1, 3]] = boxes[:, [1, 3]].clip(0, h - 1)
    return boxes


def nms(boxes, scores, iou_threshold):
    if boxes.size == 0:
        return []

    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)
    order = scores.argsort()[::-1]

    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)

        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        inter_w = np.maximum(0, xx2 - xx1)
        inter_h = np.maximum(0, yy2 - yy1)
        inter = inter_w * inter_h
        union = areas[i] + areas[order[1:]] - inter
        iou = inter / np.maximum(union, 1e-6)

        order = order[np.where(iou <= iou_threshold)[0] + 1]

    return keep


def dfl(position):
    n, c, h, w = position.shape
    p_num = 4
    mc = c // p_num
    y = position.reshape(n, p_num, mc, h, w)
    e_y = np.exp(y - np.max(y, axis=2, keepdims=True))
    y = e_y / np.sum(e_y, axis=2, keepdims=True)
    acc = np.arange(mc, dtype=np.float32).reshape(1, 1, mc, 1, 1)
    return (y * acc).sum(axis=2)


def box_process(position, img_size=DEFAULT_IMG_SIZE):
    grid_h, grid_w = position.shape[2:4]
    col, row = np.meshgrid(np.arange(0, grid_w), np.arange(0, grid_h))
    col = col.reshape(1, 1, grid_h, grid_w)
    row = row.reshape(1, 1, grid_h, grid_w)
    grid = np.concatenate((col, row), axis=1)
    stride = np.array([img_size // grid_h, img_size // grid_w]).reshape(1, 2, 1, 1)

    position = dfl(position)
    box_xy = grid + 0.5 - position[:, 0:2, :, :]
    box_xy2 = grid + 0.5 + position[:, 2:4, :, :]
    return np.concatenate((box_xy * stride, box_xy2 * stride), axis=1)


def sp_flatten(tensor):
    ch = tensor.shape[1]
    tensor = tensor.transpose(0, 2, 3, 1)
    return tensor.reshape(-1, ch)


def normalize_yolo_output(output):
    pred = output
    if isinstance(output, (list, tuple)):
        if len(output) != 1:
            raise ValueError("expected one YOLO output tensor, got {}".format(len(output)))
        pred = output[0]

    pred = np.asarray(pred)
    if pred.ndim == 3:
        pred = pred[0]
    if pred.ndim != 2:
        raise ValueError("expected 2D/3D YOLO output, got shape {}".format(pred.shape))

    if pred.shape[0] < pred.shape[1]:
        pred = pred.T

    return pred.astype(np.float32, copy=False)


def postprocess_split_yolo(
    outputs,
    conf_threshold=0.25,
    iou_threshold=0.45,
    ratio=1.0,
    padding=(0, 0),
    image_shape=None,
    labels=None,
    img_size=DEFAULT_IMG_SIZE,
    max_det=300,
):
    if len(outputs) % 3 != 0:
        raise ValueError("split YOLO output count must be multiple of 3, got {}".format(len(outputs)))

    boxes = []
    class_confs = []
    branch_count = len(outputs) // 3

    for i in range(branch_count):
        box_output = np.asarray(outputs[i * 3], dtype=np.float32)
        cls_output = np.asarray(outputs[i * 3 + 1], dtype=np.float32)
        boxes.append(sp_flatten(box_process(box_output, img_size=img_size)))
        class_confs.append(sp_flatten(cls_output))

    boxes = np.concatenate(boxes)
    class_confs = np.concatenate(class_confs)
    class_count = class_confs.shape[1]

    scores = class_confs.max(axis=1)
    class_ids = class_confs.argmax(axis=1)
    keep = scores >= conf_threshold
    if not np.any(keep):
        return np.empty((0, 4)), np.empty((0,), dtype=np.int64), np.empty((0,)), class_count

    boxes = boxes[keep]
    scores = scores[keep]
    class_ids = class_ids[keep]

    if image_shape is not None:
        boxes = scale_boxes(boxes, ratio, padding, image_shape)

    final_indices = []
    for class_id in np.unique(class_ids):
        class_pos = np.where(class_ids == class_id)[0]
        class_keep = nms(boxes[class_pos], scores[class_pos], iou_threshold)
        final_indices.extend(class_pos[class_keep])

    if not final_indices:
        return np.empty((0, 4)), np.empty((0,), dtype=np.int64), np.empty((0,)), class_count

    final_indices = np.asarray(final_indices)
    order = scores[final_indices].argsort()[::-1]
    final_indices = final_indices[order][:max_det]

    if labels is not None and len(labels) != class_count:
        raise ValueError(
            "labels count ({}) does not match model classes ({})".format(
                len(labels),
                class_count,
            )
        )

    return boxes[final_indices], class_ids[final_indices], scores[final_indices], class_count


def postprocess_yolo11(
    output,
    conf_threshold=0.25,
    iou_threshold=0.45,
    ratio=1.0,
    padding=(0, 0),
    image_shape=None,
    labels=None,
    has_objectness=False,
    apply_sigmoid=False,
    max_det=300,
):
    pred = normalize_yolo_output(output)
    if pred.shape[1] < 5:
        raise ValueError("YOLO output has too few channels: {}".format(pred.shape))

    if has_objectness:
        boxes_xywh = pred[:, :4]
        class_scores = pred[:, 5:]
        obj_scores = pred[:, 4]
        if apply_sigmoid:
            class_scores = sigmoid(class_scores)
            obj_scores = sigmoid(obj_scores)
        scores = class_scores.max(axis=1) * obj_scores
        class_ids = class_scores.argmax(axis=1)
    else:
        boxes_xywh = pred[:, :4]
        class_scores = pred[:, 4:]
        if apply_sigmoid:
            class_scores = sigmoid(class_scores)
        scores = class_scores.max(axis=1)
        class_ids = class_scores.argmax(axis=1)

    keep = scores >= conf_threshold
    if not np.any(keep):
        class_count = class_scores.shape[1]
        return np.empty((0, 4)), np.empty((0,), dtype=np.int64), np.empty((0,)), class_count

    boxes = xywh_to_xyxy(boxes_xywh[keep])
    scores = scores[keep]
    class_ids = class_ids[keep]
    class_count = class_scores.shape[1]

    if image_shape is not None:
        boxes = scale_boxes(boxes, ratio, padding, image_shape)

    final_indices = []
    for class_id in np.unique(class_ids):
        class_pos = np.where(class_ids == class_id)[0]
        class_keep = nms(boxes[class_pos], scores[class_pos], iou_threshold)
        final_indices.extend(class_pos[class_keep])

    if not final_indices:
        return np.empty((0, 4)), np.empty((0,), dtype=np.int64), np.empty((0,)), class_count

    final_indices = np.asarray(final_indices)
    order = scores[final_indices].argsort()[::-1]
    final_indices = final_indices[order][:max_det]

    if labels is not None and len(labels) != class_count:
        raise ValueError(
            "labels count ({}) does not match model classes ({})".format(
                len(labels),
                class_count,
            )
        )

    return boxes[final_indices], class_ids[final_indices], scores[final_indices], class_count


def postprocess_auto(
    outputs,
    conf_threshold=0.25,
    iou_threshold=0.45,
    ratio=1.0,
    padding=(0, 0),
    image_shape=None,
    labels=None,
    has_objectness=False,
    apply_sigmoid=False,
    img_size=DEFAULT_IMG_SIZE,
    max_det=300,
):
    if len(outputs) == 1:
        return postprocess_yolo11(
            outputs,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            ratio=ratio,
            padding=padding,
            image_shape=image_shape,
            labels=labels,
            has_objectness=has_objectness,
            apply_sigmoid=apply_sigmoid,
            max_det=max_det,
        )

    return postprocess_split_yolo(
        outputs,
        conf_threshold=conf_threshold,
        iou_threshold=iou_threshold,
        ratio=ratio,
        padding=padding,
        image_shape=image_shape,
        labels=labels,
        img_size=img_size,
        max_det=max_det,
    )


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def color_for_class(class_id):
    palette = (
        (255, 56, 56),
        (56, 255, 56),
        (56, 128, 255),
        (255, 178, 56),
        (180, 56, 255),
        (56, 255, 220),
        (255, 56, 180),
        (180, 255, 56),
    )
    return palette[int(class_id) % len(palette)]


def draw_detections(image, boxes, class_ids, scores, labels):
    for box, class_id, score in zip(boxes, class_ids, scores):
        x1, y1, x2, y2 = box.astype(int)
        color = color_for_class(class_id)
        label = "{} {:.2f}".format(labels[int(class_id)], float(score))

        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)

        text_size, baseline = cv2.getTextSize(
            label,
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            2,
        )
        text_w, text_h = text_size
        text_y = y1 - 8 if y1 - text_h - baseline - 8 > 0 else y1 + text_h + baseline + 8
        box_y1 = text_y - text_h - baseline
        box_y2 = text_y + baseline
        cv2.rectangle(image, (x1, box_y1), (x1 + text_w + 6, box_y2), color, -1)
        cv2.putText(
            image,
            label,
            (x1 + 3, text_y - baseline),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 0),
            2,
            cv2.LINE_AA,
        )

    return image


def extract_color_features(image, boxes, class_ids, scores, labels):
    features = []
    height, width = image.shape[:2]

    for index, (box, class_id, score) in enumerate(zip(boxes, class_ids, scores)):
        x1, y1, x2, y2 = box.astype(int)
        x1 = max(0, min(width - 1, x1))
        x2 = max(0, min(width - 1, x2))
        y1 = max(0, min(height - 1, y1))
        y2 = max(0, min(height - 1, y2))
        if x2 <= x1 or y2 <= y1:
            continue

        roi = image[y1:y2 + 1, x1:x2 + 1]
        if roi.size == 0:
            continue

        b_mean, g_mean, r_mean = roi.reshape(-1, 3).mean(axis=0)
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        h_mean, s_mean, v_mean = hsv.reshape(-1, 3).mean(axis=0)

        features.append(
            {
                "detection_id": index,
                "label": labels[int(class_id)],
                "confidence": float(score),
                "x1": int(x1),
                "y1": int(y1),
                "x2": int(x2),
                "y2": int(y2),
                "area_px": int((x2 - x1 + 1) * (y2 - y1 + 1)),
                "rgb_r_mean": float(r_mean),
                "rgb_g_mean": float(g_mean),
                "rgb_b_mean": float(b_mean),
                "hsv_h_mean_deg": float(h_mean) * 2.0,
                "hsv_s_mean_pct": float(s_mean) * 100.0 / 255.0,
                "hsv_v_mean_pct": float(v_mean) * 100.0 / 255.0,
            }
        )

    return features


class YOLO11RKNNDetector:
    def __init__(
        self,
        img_size=DEFAULT_IMG_SIZE,
        conf_threshold=0.25,
        iou_threshold=0.45,
        labels=None,
        input_format="nhwc",
        has_objectness=False,
        apply_sigmoid=False,
        max_det=300,
    ):
        self.img_size = img_size
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.labels = labels
        self.input_format = input_format.lower()
        self.has_objectness = has_objectness
        self.apply_sigmoid = apply_sigmoid
        self.max_det = max_det

        if self.input_format not in ("nhwc", "nchw"):
            raise ValueError("input_format must be nhwc or nchw")

    def preprocess(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb, ratio, padding = letterbox(rgb, (self.img_size, self.img_size))
        if self.input_format == "nchw":
            tensor = np.expand_dims(rgb.transpose(2, 0, 1), axis=0)
        else:
            tensor = np.expand_dims(rgb, axis=0)
        return tensor, ratio, padding

    def infer(self, rknn, frame):
        tensor, ratio, padding = self.preprocess(frame)
        outputs = rknn.inference(inputs=[tensor], data_format=[self.input_format])
        boxes, class_ids, scores, class_count = postprocess_auto(
            outputs,
            conf_threshold=self.conf_threshold,
            iou_threshold=self.iou_threshold,
            ratio=ratio,
            padding=padding,
            image_shape=frame.shape,
            labels=self.labels,
            has_objectness=self.has_objectness,
            apply_sigmoid=self.apply_sigmoid,
            img_size=self.img_size,
            max_det=self.max_det,
        )

        if self.labels is None:
            self.labels = make_default_labels(class_count)

        color_features = extract_color_features(frame, boxes, class_ids, scores, self.labels)
        return draw_detections(frame, boxes, class_ids, scores, self.labels), len(scores), color_features
