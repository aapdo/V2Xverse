#!/usr/bin/env python3
"""Zero-shot V2Xverse/CoDriving multi-agent diagnostic runner.

This script intentionally does not train or update model weights. It loads the
official CoDriving perception/planner checkpoints, monkey-patches the V2Xverse
perception dataset retrieval path, and applies source-level corruptions before
the normal forward pass.
"""

import argparse
import csv
import hashlib
import io
import json
import logging
import os
import statistics
import sys
import time
from collections import OrderedDict, defaultdict
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageEnhance, ImageFilter
from torch.utils.data import DataLoader, Subset

import opencood.hypes_yaml.yaml_utils as yaml_utils
from opencood.data_utils.datasets import build_dataset
from opencood.tools import train_utils
from opencood.utils import eval_utils
from opencood.utils.occ_render import box2occ

from common.detection import warp_image
from common.io import load_config_from_yaml
from common.registry import build_object_within_registry_from_config
from common.torch_helper import load_checkpoint
from codriving import CODRIVING_REGISTRY
from codriving.models.model_decoration import decorate_model
from codriving.utils.torch_helper import build_dataloader, move_dict_data_to_device


torch.multiprocessing.set_sharing_strategy("file_system")
LOG = logging.getLogger("v2xverse_diag")
DIAG_CONTEXT = None
_PATCH_INSTALLED = False


def stable_int(*parts):
    key = "|".join(str(p) for p in parts)
    return int(hashlib.sha1(key.encode("utf-8")).hexdigest()[:12], 16)


def as_float(x):
    if isinstance(x, torch.Tensor):
        return float(x.detach().cpu().item())
    if isinstance(x, np.generic):
        return float(x)
    return float(x)


def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def zero_image_like(img):
    if img is None:
        return None
    if not isinstance(img, Image.Image):
        return img
    return Image.new(img.mode, img.size, 0)


def image_to_hashable_stats(img):
    if not isinstance(img, Image.Image):
        return {}
    arr = np.asarray(img)
    return {
        "image_mean": float(arr.mean()) if arr.size else 0.0,
        "image_std": float(arr.std()) if arr.size else 0.0,
    }


def make_null_lidar(lidar_np):
    """Return a near-empty point cloud that still keeps one sparse-conv slot.

    Completely empty or all-origin cooperative point clouds can be filtered out
    before sparse convolution. CoDriving still keeps the source in record_len
    and the pairwise transform matrix, so the feature batch and transform batch
    dimensions diverge. A single zero-intensity point at the detector corner is
    effectively uninformative for planning while preserving the batch slot.
    """
    feature_dim = 4
    dtype = np.float32
    if isinstance(lidar_np, np.ndarray) and lidar_np.ndim == 2:
        feature_dim = max(int(lidar_np.shape[1]), 4)
        dtype = lidar_np.dtype if np.issubdtype(lidar_np.dtype, np.floating) else np.float32

    sentinel = np.zeros((1, feature_dim), dtype=dtype)
    sentinel[0, 0] = 35.5
    sentinel[0, 1] = 11.5
    sentinel[0, 2] = 0.0
    if feature_dim > 3:
        sentinel[0, 3] = 0.0
    return sentinel


def agent_type(cav_id):
    if cav_id == "car_0":
        return "ego"
    if cav_id.startswith("rsu"):
        return "rsu"
    if cav_id.startswith("car_"):
        return "cav"
    return "unknown"


def severity_value(severity, table, default=None):
    if severity in table:
        return table[severity]
    if default is not None:
        return default
    if "s2" in table:
        return table["s2"]
    return next(iter(table.values()))


class CsvWriter:
    def __init__(self, path, fieldnames):
        self.path = Path(path)
        ensure_dir(self.path.parent)
        self.fieldnames = fieldnames
        self.fh = self.path.open("w", newline="")
        self.writer = csv.DictWriter(self.fh, fieldnames=fieldnames, extrasaction="ignore")
        self.writer.writeheader()

    def write(self, row):
        self.writer.writerow({k: row.get(k, "") for k in self.fieldnames})

    def write_many(self, rows):
        for row in rows:
            self.write(row)

    def close(self):
        self.fh.flush()
        self.fh.close()


class DiagnosticContext:
    def __init__(self, args):
        self.args = args
        self.run_id = args.run_id
        self.setting = args.setting
        self.shift_family = args.shift_family or "none"
        self.severity = args.severity or "none"
        self.application_mode = args.application_mode or "none"
        self.shift_seed = args.shift_seed
        self.audit_rows = []
        self.agent_rows = []

    def rng(self, route_id, frame_id, cav_id, salt):
        seed = stable_int(self.shift_seed, self.run_id, route_id, frame_id, cav_id, salt) % (2**32)
        return np.random.default_rng(seed)

    def source_allowed_by_setting(self, cav_id):
        t = agent_type(cav_id)
        if t == "ego":
            return True
        if self.setting in {"ego_only", "null_all_missing_flag"}:
            return False
        if self.setting == "clean_rsu_only":
            return t == "rsu"
        if self.setting == "clean_vehicle_only":
            return t == "cav"
        return True

    def source_zeroed_by_setting(self, cav_id):
        t = agent_type(cav_id)
        if t == "ego":
            return False
        if self.setting in {"null_all_image", "all_null"}:
            return True
        if self.setting == "null_rsu_only":
            return t == "rsu"
        if self.setting == "null_vehicle_only":
            return t == "cav"
        return False

    def should_shift(self, cav_id):
        if self.shift_family in {"", "none", None}:
            return False
        t = agent_type(cav_id)
        if t == "ego":
            return False
        mode = self.application_mode
        if mode in {"all_shifted", "mixed_severity"}:
            return True
        if mode == "rsu_shifted_only":
            return t == "rsu"
        if mode == "vehicle_shifted_only":
            return t == "cav"
        if mode == "one_null_one_clean":
            return t == "rsu"
        return True

    def apply(self, dataset, data, idx=None, tpe="all", data_dir=None):
        if not isinstance(data, OrderedDict) or "car_0" not in data:
            return data
        scene_dict = data["car_0"].get("scene_dict")
        frame_id = data["car_0"].get("frame_id")
        route_id = "unknown"
        if scene_dict and scene_dict.get("ego"):
            route_id = str(Path(scene_dict["ego"]).parent)

        removed = []
        for cav_id in list(data.keys()):
            if not self.source_allowed_by_setting(cav_id):
                removed.append(cav_id)
                data.pop(cav_id, None)

        for cav_id in list(data.keys()):
            if cav_id == "car_0":
                continue
            action = "clean"
            params = {}
            if self.source_zeroed_by_setting(cav_id):
                self.zero_agent(data[cav_id])
                action = "zeroed_by_setting"
            elif self.should_shift(cav_id):
                action, params = self.apply_shift(dataset, data, cav_id, scene_dict, frame_id, route_id, tpe)

            if tpe == "all":
                self.agent_rows.append(self.agent_row(route_id, frame_id, cav_id, data.get(cav_id), action, params))

        if tpe == "all":
            for cav_id in removed:
                self.agent_rows.append(self.agent_row(route_id, frame_id, cav_id, None, "removed_by_setting", {}))
        return data

    def agent_row(self, route_id, frame_id, cav_id, record, action, params):
        row = {
            "run_id": self.run_id,
            "setting": self.setting,
            "shift_family": self.shift_family,
            "severity": self.severity,
            "application_mode": self.application_mode,
            "shift_seed": self.shift_seed,
            "route_id": route_id,
            "frame_id": frame_id,
            "agent_id": cav_id,
            "agent_type": agent_type(cav_id),
            "agent_available": record is not None,
            "agent_shifted": action not in {"clean", "removed_by_setting"},
            "agent_action": action,
        }
        row.update(params)
        if record is not None and "params" in record:
            pose = record["params"].get("lidar_pose", ["", "", "", "", "", ""])
            row.update({
                "source_pose_x": pose[0],
                "source_pose_y": pose[1],
                "source_yaw": pose[4] if len(pose) > 4 else "",
            })
            if "lidar_np" in record:
                row["source_valid_lidar_points"] = int(np.count_nonzero(np.linalg.norm(record["lidar_np"][:, :3], axis=1)))
            if "rgb_front" in record:
                row.update(image_to_hashable_stats(record["rgb_front"]))
        return row

    def zero_agent(self, record):
        for key in ("rgb_front", "rgb_left", "rgb_right", "rgb_rear"):
            if key in record:
                record[key] = zero_image_like(record[key])
        if "camera_data" in record:
            record["camera_data"] = [zero_image_like(img) for img in record["camera_data"]]
        if "lidar_np" in record and isinstance(record["lidar_np"], np.ndarray):
            record["lidar_np"] = make_null_lidar(record["lidar_np"])

    def replace_with_delayed_record(self, dataset, data, cav_id, scene_dict, frame_id, delay, tpe):
        if scene_dict is None or frame_id is None:
            return False
        delayed_frame = max(0, int(frame_id) - int(delay))
        try:
            if cav_id.startswith("car_") and cav_id != "car_0":
                idx = int(cav_id.split("_")[1]) - 1
                route_dir = scene_dict["other_egos"][idx]
                data[cav_id] = dataset.get_one_record(route_dir, delayed_frame, agent="other_ego", visible_actors=None, tpe=tpe)
                return True
            if cav_id.startswith("rsu"):
                idx = int(cav_id.split("_")[1])
                route_dir = scene_dict["rsu"][idx]
                data[cav_id] = dataset.get_one_record(route_dir, delayed_frame, agent="rsu", visible_actors=None, tpe=tpe)
                return True
        except Exception as exc:
            LOG.warning("failed delayed source replacement cav=%s frame=%s delay=%s: %s", cav_id, frame_id, delay, exc)
        return False

    def apply_shift(self, dataset, data, cav_id, scene_dict, frame_id, route_id, tpe):
        record = data[cav_id]
        family = self.shift_family
        severity = self.severity
        rng = self.rng(route_id, frame_id, cav_id, family)
        params = {}

        if family == "latency_det":
            delay = severity_value(severity, {"s1": 1, "s2": 3, "s3": 5, "stress": 10})
            ok = self.replace_with_delayed_record(dataset, data, cav_id, scene_dict, frame_id, delay, tpe)
            return ("latency_det" if ok else "latency_det_failed", {"delay_frames": delay})

        if family == "latency_jitter":
            choices = severity_value(severity, {
                "s1": [0, 1],
                "s2": [0, 1, 2, 3],
                "s3": [1, 2, 3, 5],
                "stress": [0, 2, 5, 10],
            })
            delay = int(rng.choice(choices))
            ok = self.replace_with_delayed_record(dataset, data, cav_id, scene_dict, frame_id, delay, tpe)
            return ("latency_jitter" if ok else "latency_jitter_failed", {"delay_frames": delay})

        if family in {"frame_lost_hold", "frame_lost_zero", "packet_drop"}:
            prob = severity_value(severity, {"s1": 0.10, "s2": 0.30, "s3": 0.50, "stress": 0.75})
            dropped = bool(rng.random() < prob)
            params.update({"drop_probability": prob, "source_packet_drop_flag": dropped})
            if dropped:
                if family == "frame_lost_hold":
                    delay = severity_value(severity, {"s1": 1, "s2": 2, "s3": 4, "stress": 8})
                    self.replace_with_delayed_record(dataset, data, cav_id, scene_dict, frame_id, delay, tpe)
                    params["held_frame_age"] = delay
                else:
                    self.zero_agent(record)
            return family, params

        if family == "pose_noise":
            pos_std, yaw_std = severity_value(severity, {
                "s1": (0.2, 0.2),
                "s2": (0.4, 0.4),
                "s3": (0.6, 0.6),
                "stress": (1.0, 1.0),
            })
            noise = np.array([rng.normal(0, pos_std), rng.normal(0, pos_std), 0, 0, rng.normal(0, yaw_std), 0])
            for pose_key in ("lidar_pose", "map_pose"):
                if pose_key in record["params"]:
                    record["params"][pose_key] = (np.asarray(record["params"][pose_key]) + noise).tolist()
            params.update({"pose_error_m": float(np.linalg.norm(noise[:2])), "yaw_error_deg": float(abs(noise[4]))})
            return family, params

        if family in {"lidar_point_drop", "bandwidth_cap"} and "lidar_np" in record:
            keep = severity_value(severity, {
                "s1": 0.75 if family == "bandwidth_cap" else 0.50,
                "s2": 0.50 if family == "bandwidth_cap" else 0.25,
                "s3": 0.25 if family == "bandwidth_cap" else 0.10,
                "stress": 0.10 if family == "bandwidth_cap" else 0.05,
            })
            lidar = record["lidar_np"]
            if lidar.shape[0] > 1:
                n_keep = max(1, int(lidar.shape[0] * keep))
                indices = rng.choice(lidar.shape[0], n_keep, replace=False)
                record["lidar_np"] = lidar[np.sort(indices)]
            params["lidar_point_keep_ratio"] = keep
            if family == "bandwidth_cap":
                self.apply_image_transform(record, "resolution", severity, rng, params)
            return family, params

        if family in {
            "fov_center", "fov_left_loss", "fov_right_loss", "fov_top_loss", "fov_bottom_loss",
            "resolution", "camera_crash", "color_quant", "brightness", "darkness", "contrast",
            "motion_blur", "defocus_blur", "jpeg", "fog", "rain", "snow",
        }:
            self.apply_image_transform(record, family, severity, rng, params)
            return family, params

        if family == "compound_lcf":
            delay = severity_value(severity, {"mild": 1, "mid": 3, "severe": 5, "stress": 10}, default=3)
            self.replace_with_delayed_record(dataset, data, cav_id, scene_dict, frame_id, delay, tpe)
            record = data[cav_id]
            self.apply_image_transform(record, "fov_center", {"mild": "s1", "mid": "s2", "severe": "s3", "stress": "stress"}.get(severity, "s2"), rng, params)
            params["delay_frames"] = delay
            return family, params

        if family == "compound_avail":
            prob = severity_value(severity, {"mild": 0.10, "mid": 0.30, "severe": 0.50, "stress": 0.75}, default=0.30)
            if rng.random() < prob:
                self.zero_agent(record)
            params["drop_probability"] = prob
            return family, params

        if family == "compound_photo_comm":
            self.apply_image_transform(record, "color_quant", {"mild": "s1", "mid": "s2", "severe": "s3", "stress": "stress"}.get(severity, "s2"), rng, params)
            if "lidar_np" in record:
                keep = severity_value(severity, {"mild": 0.75, "mid": 0.50, "severe": 0.25, "stress": 0.10}, default=0.50)
                lidar = record["lidar_np"]
                if lidar.shape[0] > 1:
                    n_keep = max(1, int(lidar.shape[0] * keep))
                    record["lidar_np"] = lidar[np.sort(rng.choice(lidar.shape[0], n_keep, replace=False))]
                params["lidar_point_keep_ratio"] = keep
            return family, params

        return "unknown_shift_noop", {}

    def apply_image_transform(self, record, family, severity, rng, params):
        for key in ("rgb_front", "rgb_left", "rgb_right", "rgb_rear"):
            if key not in record or not isinstance(record[key], Image.Image):
                continue
            record[key] = transform_image(record[key], family, severity, rng, params)
        if "camera_data" in record:
            record["camera_data"] = [
                transform_image(img, family, severity, rng, params) if isinstance(img, Image.Image) else img
                for img in record["camera_data"]
            ]


def transform_image(img, family, severity, rng, params):
    if family == "camera_crash":
        crash_fraction = severity_value(severity, {"s1": 0.25, "s2": 0.50, "s3": 1.0, "stress": 1.0})
        params["camera_crash_probability"] = crash_fraction
        if rng.random() < crash_fraction:
            return zero_image_like(img)
        return img

    arr = np.asarray(img.convert("RGB")).copy()
    h, w = arr.shape[:2]

    if family == "fov_center":
        keep = severity_value(severity, {"s1": 0.90, "s2": 0.70, "s3": 0.50, "stress": 0.30})
        y0 = int((1 - keep) * h / 2)
        y1 = h - y0
        x0 = int((1 - keep) * w / 2)
        x1 = w - x0
        masked = np.zeros_like(arr)
        masked[y0:y1, x0:x1] = arr[y0:y1, x0:x1]
        params["fov_keep_ratio"] = keep
        return Image.fromarray(masked)

    if family.startswith("fov_") and family.endswith("_loss"):
        frac = severity_value(severity, {"s1": 0.20, "s2": 0.40, "s3": 0.60, "stress": 0.70})
        side = family.replace("fov_", "").replace("_loss", "")
        if side == "left":
            arr[:, : int(w * frac)] = 0
        elif side == "right":
            arr[:, int(w * (1 - frac)):] = 0
        elif side == "top":
            arr[: int(h * frac), :] = 0
        elif side == "bottom":
            arr[int(h * (1 - frac)):, :] = 0
        params.update({"masked_side": side, "masked_pixel_ratio": frac})
        return Image.fromarray(arr)

    if family == "resolution":
        ratio = severity_value(severity, {"s1": 0.75, "s2": 0.50, "s3": 0.25, "stress": 0.125})
        small = img.resize((max(1, int(w * ratio)), max(1, int(h * ratio))), Image.BILINEAR)
        params["downsample_ratio"] = ratio
        return small.resize((w, h), Image.BILINEAR)

    if family == "color_quant":
        bits = severity_value(severity, {"s1": 6, "s2": 4, "s3": 3, "stress": 2})
        shift = 8 - int(bits)
        params["bits_per_channel"] = bits
        return Image.fromarray(((arr >> shift) << shift).astype(np.uint8))

    if family in {"brightness", "darkness"}:
        scale = severity_value(severity, {"s1": 1.3, "s2": 1.6, "s3": 2.0, "stress": 2.5}) if family == "brightness" else severity_value(severity, {"s1": 0.7, "s2": 0.4, "s3": 0.2, "stress": 0.1})
        params["brightness_scale"] = scale
        return ImageEnhance.Brightness(img).enhance(scale)

    if family == "contrast":
        scale = severity_value(severity, {"s1": 0.75, "s2": 0.50, "s3": 0.25, "stress": 0.10})
        params["contrast_scale"] = scale
        return ImageEnhance.Contrast(img).enhance(scale)

    if family == "motion_blur":
        k = severity_value(severity, {"s1": 5, "s2": 9, "s3": 15, "stress": 21})
        kernel = [0.0] * (k * k)
        for i in range(k):
            kernel[(k // 2) * k + i] = 1.0 / k
        params["blur_kernel"] = k
        return img.filter(ImageFilter.Kernel((k, k), kernel))

    if family == "defocus_blur":
        radius = severity_value(severity, {"s1": 1, "s2": 2, "s3": 3, "stress": 5})
        params["blur_kernel"] = radius
        return img.filter(ImageFilter.GaussianBlur(radius=radius))

    if family == "jpeg":
        quality = severity_value(severity, {"s1": 70, "s2": 40, "s3": 20, "stress": 10})
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=int(quality))
        buf.seek(0)
        params["jpeg_quality"] = quality
        return Image.open(buf).convert("RGB")

    if family in {"fog", "snow"}:
        alpha = severity_value(severity, {"s1": 0.15, "s2": 0.30, "s3": 0.50, "stress": 0.75})
        white = np.full_like(arr, 255)
        params[f"{family}_strength"] = alpha
        return Image.fromarray(np.clip((1 - alpha) * arr + alpha * white, 0, 255).astype(np.uint8))

    if family == "rain":
        alpha = severity_value(severity, {"s1": 0.08, "s2": 0.15, "s3": 0.25, "stress": 0.35})
        overlay = arr.copy()
        for _ in range(int(alpha * 400)):
            x = int(rng.integers(0, w))
            y = int(rng.integers(0, h))
            length = int(rng.integers(6, 18))
            overlay[y:min(h, y + length), max(0, x - 1):min(w, x + 1)] = 200
        params["rain_strength"] = alpha
        return Image.blend(Image.fromarray(arr), Image.fromarray(overlay), 0.45)

    return img


def install_dataset_patch():
    global _PATCH_INSTALLED
    if _PATCH_INSTALLED:
        return
    from opencood.data_utils.datasets.basedataset.v2xverse_basedataset import V2XVERSEBaseDataset

    original = V2XVERSEBaseDataset.retrieve_base_data

    def retrieve_base_data_with_diag(self, idx, tpe="all", extra_source=None, data_dir=None):
        data = original(self, idx, tpe=tpe, extra_source=extra_source, data_dir=data_dir)
        if DIAG_CONTEXT is None or extra_source is not None:
            return data
        return DIAG_CONTEXT.apply(self, data, idx=idx, tpe=tpe, data_dir=data_dir)

    V2XVERSEBaseDataset.retrieve_base_data = retrieve_base_data_with_diag
    _PATCH_INSTALLED = True


def init_wandb(args, run_dir, summary_config):
    if args.wandb_mode == "disabled":
        return None
    mode = args.wandb_mode
    if mode == "auto":
        has_netrc = Path.home().joinpath(".netrc").exists()
        has_key = bool(os.environ.get("WANDB_API_KEY"))
        mode = "online" if has_netrc or has_key else "offline"
    # The wandb SDK reads WANDB_MODE from the environment and does not
    # understand our wrapper-level "auto" value. Normalize it before init.
    os.environ["WANDB_MODE"] = mode
    try:
        import wandb
    except Exception as exc:
        LOG.warning("wandb import failed, continuing without wandb: %s", exc)
        return None
    return wandb.init(
        project=args.wandb_project,
        entity=args.wandb_entity or None,
        name=args.run_id,
        dir=str(run_dir),
        mode=mode,
        config=summary_config,
        reinit=True,
    )


def build_result_stat():
    result_stat = {}
    for c in [0, 1, 3]:
        result_stat[c] = {
            0.3: {"tp": [], "fp": [], "gt": 0, "score": []},
            0.5: {"tp": [], "fp": [], "gt": 0, "score": []},
            0.7: {"tp": [], "fp": [], "gt": 0, "score": []},
        }
    return result_stat


def per_frame_perception_row(run_id, sample_idx, frame, infer_result, comm_rate):
    row = {
        "run_id": run_id,
        "sample_idx": sample_idx,
        "frame_offset": frame,
        "comm_rate": comm_rate,
    }
    pred = infer_result.get("pred_box_tensor")
    gt = infer_result.get("gt_box_tensor")
    for idx, cls_id in enumerate([0, 1, 3]):
        pred_boxes = pred[idx] if pred is not None and len(pred) > idx else None
        gt_boxes = gt[idx] if gt is not None and len(gt) > idx else None
        row[f"num_pred_class_{cls_id}"] = 0 if pred_boxes is None else int(pred_boxes.shape[0])
        row[f"num_gt_class_{cls_id}"] = 0 if gt_boxes is None else int(gt_boxes.shape[0])
    return row


def filter_ego_car(infer_result):
    if infer_result["pred_box_tensor"][0] is None:
        return infer_result
    import copy

    box_filte_ego_car_list = []
    score_filte_ego_car_list = []
    num_car = infer_result["pred_box_tensor"][0].shape[0]
    for car_actor_id in range(num_car):
        car_box = copy.deepcopy(infer_result["pred_box_tensor"][0][car_actor_id])
        car_box = car_box.cpu().numpy()
        car_box[:, 0] += 1.3
        location_box = np.mean(car_box[:4, :2], 0)
        if np.linalg.norm(location_box) < 1.4:
            continue
        box_filte_ego_car_list.append(infer_result["pred_box_tensor"][0][car_actor_id])
        score_filte_ego_car_list.append(infer_result["pred_score"][0][car_actor_id])
    infer_result["pred_box_tensor"][0] = torch.stack(box_filte_ego_car_list, dim=0) if box_filte_ego_car_list else None
    infer_result["pred_score"][0] = torch.stack(score_filte_ego_car_list, dim=0) if score_filte_ego_car_list else None
    return infer_result


def run(args):
    global DIAG_CONTEXT
    run_dir = Path(args.out_root) / args.run_id
    ensure_dir(run_dir)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(run_dir / "run.log")],
    )
    DIAG_CONTEXT = DiagnosticContext(args)
    install_dataset_patch()

    config_for_manifest = vars(args).copy()
    wandb_run = init_wandb(args, run_dir, config_for_manifest)

    manifest_writer = CsvWriter(run_dir / "manifest.csv", [
        "run_id", "date", "host", "gpu", "dataset", "task", "model",
        "checkpoint_perception", "checkpoint_planning", "setting",
        "shift_family", "severity", "application_mode", "shift_seed",
        "max_samples", "start_index", "stride", "workers",
    ])
    planning_writer = CsvWriter(run_dir / "per_sample_planning.csv", [
        "run_id", "sample_idx", "route_id", "frame_id", "setting", "shift_family",
        "severity", "application_mode", "shift_seed", "ADE", "FDE",
        "ADE_1s", "ADE_2s", "ADE_3s", "ADE_4s", "FDE_horizon",
        "pred_waypoints", "gt_waypoints",
    ])
    perception_writer = CsvWriter(run_dir / "per_sample_perception.csv", [
        "run_id", "sample_idx", "frame_offset", "comm_rate",
        "num_pred_class_0", "num_gt_class_0", "num_pred_class_1", "num_gt_class_1",
        "num_pred_class_3", "num_gt_class_3",
    ])

    host = os.uname().nodename
    gpu = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    manifest_writer.write({
        "run_id": args.run_id,
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "host": host,
        "gpu": gpu,
        "dataset": "V2Xverse",
        "task": "waypoint_prediction+perception_proxy",
        "model": "CoDriving",
        "checkpoint_perception": args.model_dir,
        "checkpoint_planning": args.planner_resume,
        "setting": args.setting,
        "shift_family": args.shift_family,
        "severity": args.severity,
        "application_mode": args.application_mode,
        "shift_seed": args.shift_seed,
        "max_samples": args.max_samples,
        "start_index": args.start_index,
        "stride": args.stride,
        "workers": args.workers,
    })

    hypes = yaml_utils.load_yaml(None, args)
    hypes["validate_dir"] = hypes["test_dir"]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    LOG.info("device=%s perception_checkpoint=%s planner=%s", device, args.model_dir, args.planner_resume)

    perception_model = train_utils.create_model(hypes)
    resume_epoch, perception_model = train_utils.load_saved_model(args.model_dir, perception_model)
    if torch.cuda.is_available():
        perception_model.cuda()
    perception_model.eval()
    LOG.info("loaded perception epoch=%s", resume_epoch)

    opencood_dataset = build_dataset(hypes, visualize=True, train=False)

    config = load_config_from_yaml(args.config_file)
    test_data_config = config["data"]["test"]
    test_data_config["dataset"]["perception_hypes"] = hypes
    test_data_config["dataloader"]["num_workers"] = args.workers
    test_data_config["dataloader"]["batch_size"] = 1
    test_dataloader = build_dataloader(test_data_config, is_distributed=False)

    if args.start_index or args.stride != 1 or args.max_samples:
        dataset_len = len(test_dataloader.dataset)
        indices = list(range(args.start_index, dataset_len, args.stride))
        if args.max_samples:
            indices = indices[: args.max_samples]
        subset = Subset(test_dataloader.dataset, indices)
        test_dataloader = DataLoader(
            subset,
            batch_size=1,
            num_workers=args.workers,
            collate_fn=test_dataloader.dataset.collate_fn,
            shuffle=False,
            pin_memory=False,
            drop_last=False,
        )
        sample_indices = indices
    else:
        sample_indices = list(range(len(test_dataloader.dataset)))
        if args.max_samples:
            sample_indices = sample_indices[: args.max_samples]
            subset = Subset(test_dataloader.dataset, sample_indices)
            test_dataloader = DataLoader(
                subset,
                batch_size=1,
                num_workers=args.workers,
                collate_fn=test_dataloader.dataset.collate_fn,
                shuffle=False,
                pin_memory=False,
                drop_last=False,
            )

    planning_model = build_object_within_registry_from_config(CODRIVING_REGISTRY, config["model"])
    decorate_model(planning_model, **config["model_decoration"])
    planning_model.to(device)
    planner_epoch = load_checkpoint(args.planner_resume, device, planning_model, strict=True)
    planning_model.eval()
    metric_func = build_object_within_registry_from_config(CODRIVING_REGISTRY, config["test_metric"])
    LOG.info("loaded planner epoch=%s samples=%s", planner_epoch, len(sample_indices))

    result_stat = build_result_stat()
    ade_values = []
    fde_values = []
    start_time = time.time()

    for loader_i, batch_data in enumerate(test_dataloader):
        sample_idx = sample_indices[loader_i] if loader_i < len(sample_indices) else loader_i
        with torch.no_grad():
            pred_batch_data, perce_batch_data_dict = batch_data
            move_dict_data_to_device(pred_batch_data, device)
            pred_batch_data.update({"fused_feature": [], "features_before_fusion": []})

            frame_list = sorted(perce_batch_data_dict.keys())
            perception_results_list = []
            occ_map_list = []

            for frame in frame_list:
                perce_batch_data_dict[frame] = train_utils.to_device(perce_batch_data_dict[frame], device)
                output_dict = OrderedDict()
                for cav_id, cav_content in perce_batch_data_dict[frame].items():
                    output_dict[cav_id] = perception_model(cav_content)

                pred_box_tensor, pred_score, gt_box_tensor = test_dataloader.dataset.dataset.perception_dataset.post_process_multiclass(
                    perce_batch_data_dict[frame], output_dict, online_eval_only=True
                ) if isinstance(test_dataloader.dataset, Subset) else test_dataloader.dataset.perception_dataset.post_process_multiclass(
                    perce_batch_data_dict[frame], output_dict, online_eval_only=True
                )

                infer_result = {
                    "pred_box_tensor": pred_box_tensor,
                    "pred_score": pred_score,
                    "gt_box_tensor": gt_box_tensor,
                }
                if "comm_rate" in output_dict["ego"]:
                    infer_result["comm_rate"] = output_dict["ego"]["comm_rate"]

                infer_result = filter_ego_car(infer_result)
                for iou in [0.3, 0.5, 0.7]:
                    eval_utils.caluclate_tp_fp_multiclass(
                        infer_result["pred_box_tensor"], infer_result["pred_score"], infer_result["gt_box_tensor"], result_stat, iou
                    )
                comm_rate = ""
                if "comm_rate" in infer_result:
                    try:
                        comm_rate = float(torch.as_tensor(infer_result["comm_rate"]).detach().cpu().mean())
                    except Exception:
                        comm_rate = ""
                perception_writer.write(per_frame_perception_row(args.run_id, sample_idx, frame, infer_result, comm_rate))

                occ_map_list.append(box2occ(infer_result))
                perception_results = output_dict["ego"]
                perception_results_list.append(perception_results)
                fused_feature_2 = perception_results["fused_feature"].permute(0, 1, 3, 2)
                fused_feature_3 = torch.flip(fused_feature_2, dims=[2])
                w = fused_feature_2.shape[3] // 2
                pred_batch_data["fused_feature"].append(fused_feature_3[:, :, :192, w - 48 : w + 48])

            pred_batch_data["feature_warpped_list"] = []
            for b in range(len(perception_results_list[0]["fused_feature"])):
                feature_dim = perception_results_list[0]["fused_feature"].shape[1]
                feature_to_warp = torch.zeros(1, 5, feature_dim, 192, 96).to(device).float()
                det_map_pose = torch.zeros(1, 5, 3).to(device).float()
                occ_to_warp = torch.zeros(1, 5, 1, 192, 96).to(device).float()
                for t in range(5):
                    feature_to_warp[0, t, :] = pred_batch_data["fused_feature"][t][b]
                    det_map_pose[:, t] = torch.tensor(pred_batch_data["detmap_pose"][b, t])
                    occ_to_warp[0, t, 0:1] = occ_map_list[t]
                feature_warped = warp_image(det_map_pose, feature_to_warp)
                pred_batch_data["feature_warpped_list"].append(feature_warped)
                occ_warped = warp_image(det_map_pose, occ_to_warp)
                pred_batch_data["occupancy"][:, :, 0, :, :] = occ_warped[:, :, 0, :, :]

            model_output = planning_model(pred_batch_data)
            ADE, FDE = metric_func(pred_batch_data, model_output)
            ade = float(ADE.detach().cpu().flatten()[0])
            fde = float(FDE.detach().cpu().flatten()[0])
            ade_values.append(ade)
            fde_values.append(fde)

            dis = torch.sum((model_output["future_waypoints"] - pred_batch_data["future_waypoints"]) ** 2, dim=2).sqrt()
            dis_np = dis.detach().cpu().numpy()[0]
            pred_wp = model_output["future_waypoints"].detach().cpu().numpy()[0]
            gt_wp = pred_batch_data["future_waypoints"].detach().cpu().numpy()[0]
            scene = None
            frame_id = ""
            route_id = ""
            base_dataset = test_dataloader.dataset.dataset if isinstance(test_dataloader.dataset, Subset) else test_dataloader.dataset
            try:
                scene, frame_id = base_dataset.route_frames[sample_idx]
                route_id = str(Path(scene["ego"]).parent)
            except Exception:
                pass
            planning_writer.write({
                "run_id": args.run_id,
                "sample_idx": sample_idx,
                "route_id": route_id,
                "frame_id": frame_id,
                "setting": args.setting,
                "shift_family": args.shift_family,
                "severity": args.severity,
                "application_mode": args.application_mode,
                "shift_seed": args.shift_seed,
                "ADE": ade,
                "FDE": fde,
                "ADE_1s": float(dis_np[:2].mean()),
                "ADE_2s": float(dis_np[:5].mean()),
                "ADE_3s": float(dis_np[:7].mean()),
                "ADE_4s": float(dis_np[:10].mean()),
                "FDE_horizon": float(dis_np[-1]),
                "pred_waypoints": json.dumps(pred_wp.tolist()) if args.save_waypoints else "",
                "gt_waypoints": json.dumps(gt_wp.tolist()) if args.save_waypoints else "",
            })

            if wandb_run is not None and (loader_i + 1) % args.wandb_log_interval == 0:
                wandb_run.log({
                    "sample/ADE": ade,
                    "sample/FDE": fde,
                    "running/mean_ADE": float(np.mean(ade_values)),
                    "running/mean_FDE": float(np.mean(fde_values)),
                    "sample_idx": sample_idx,
                }, step=loader_i + 1)

            if (loader_i + 1) % args.log_interval == 0:
                LOG.info("progress %s/%s mean_ADE=%.4f mean_FDE=%.4f", loader_i + 1, len(sample_indices), np.mean(ade_values), np.mean(fde_values))

            torch.cuda.empty_cache()

    agent_writer = CsvWriter(run_dir / "per_sample_agent.csv", [
        "run_id", "setting", "shift_family", "severity", "application_mode",
        "shift_seed", "route_id", "frame_id", "agent_id", "agent_type",
        "agent_available", "agent_shifted", "agent_action", "source_pose_x",
        "source_pose_y", "source_yaw", "source_valid_lidar_points", "image_mean",
        "image_std", "delay_frames", "drop_probability", "source_packet_drop_flag",
        "held_frame_age", "pose_error_m", "yaw_error_deg", "lidar_point_keep_ratio",
        "fov_keep_ratio", "masked_side", "masked_pixel_ratio", "downsample_ratio",
        "bits_per_channel", "brightness_scale", "contrast_scale", "blur_kernel",
        "jpeg_quality", "camera_crash_probability",
    ])
    agent_writer.write_many(DIAG_CONTEXT.agent_rows)
    agent_writer.close()

    ap_summary = {}
    for cls_id, stats in result_stat.items():
        ap_summary[str(cls_id)] = {}
        for iou in [0.3, 0.5, 0.7]:
            if stats[iou]["gt"] > 0 and len(stats[iou]["score"]) > 0:
                ap, _, _ = eval_utils.calculate_ap(stats, iou)
            else:
                ap = 0.0
            ap_summary[str(cls_id)][str(iou)] = float(ap)

    summary = {
        "run_id": args.run_id,
        "setting": args.setting,
        "shift_family": args.shift_family,
        "severity": args.severity,
        "application_mode": args.application_mode,
        "shift_seed": args.shift_seed,
        "num_samples": len(ade_values),
        "mean_ADE": float(np.mean(ade_values)) if ade_values else None,
        "median_ADE": float(np.median(ade_values)) if ade_values else None,
        "p90_ADE": float(np.percentile(ade_values, 90)) if ade_values else None,
        "p95_ADE": float(np.percentile(ade_values, 95)) if ade_values else None,
        "mean_FDE": float(np.mean(fde_values)) if fde_values else None,
        "p90_FDE": float(np.percentile(fde_values, 90)) if fde_values else None,
        "p95_FDE": float(np.percentile(fde_values, 95)) if fde_values else None,
        "perception_AP": ap_summary,
        "elapsed_sec": time.time() - start_time,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))

    manifest_writer.close()
    planning_writer.close()
    perception_writer.close()

    if wandb_run is not None:
        wandb_run.summary.update(summary)
        try:
            import wandb

            artifact = wandb.Artifact(args.run_id, type="codriving-diagnostic")
            for name in ["manifest.csv", "per_sample_planning.csv", "per_sample_perception.csv", "per_sample_agent.csv", "summary.json"]:
                artifact.add_file(str(run_dir / name))
            wandb_run.log_artifact(artifact)
        except Exception as exc:
            LOG.warning("wandb artifact logging failed: %s", exc)
        wandb_run.finish()

    LOG.info("done run_id=%s mean_ADE=%s mean_FDE=%s out=%s", args.run_id, summary["mean_ADE"], summary["mean_FDE"], run_dir)
    return summary


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--setting", default="clean_all")
    parser.add_argument("--shift-family", default="none")
    parser.add_argument("--severity", default="none")
    parser.add_argument("--application-mode", default="none")
    parser.add_argument("--shift-seed", type=int, default=0)
    parser.add_argument("--model_dir", "--model-dir", dest="model_dir", default="checkpoints/codriving/perception")
    parser.add_argument("--planner_resume", "--planner-resume", dest="planner_resume", default="checkpoints/codriving/planner/codriving_planner.ckpt")
    parser.add_argument("--config-file", default="codriving/hypes_yaml/codriving/end2end_codriving.yaml")
    parser.add_argument("--fusion_method", "--fusion-method", dest="fusion_method", default="intermediate")
    parser.add_argument("--out-root", default="experiments/v2xverse_codriving_diag/results/manual")
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--max-samples", type=int, default=0)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--stride", type=int, default=1)
    parser.add_argument("--log-interval", type=int, default=25)
    parser.add_argument("--wandb-log-interval", type=int, default=10)
    parser.add_argument("--wandb-project", default=os.environ.get("WANDB_PROJECT", "v2xverse-codriving-zero-shot"))
    parser.add_argument("--wandb-entity", default=os.environ.get("WANDB_ENTITY", ""))
    parser.add_argument("--wandb-mode", choices=["auto", "online", "offline", "disabled"], default=os.environ.get("WANDB_MODE", "auto"))
    parser.add_argument("--save-waypoints", action="store_true")
    parser.add_argument("--note", default="")
    parser.add_argument("--modal", type=int, default=0)
    parser.add_argument("--range", default="140.8,40")
    parser.add_argument("--no_score", action="store_true")
    parser.add_argument("--skip_frames", type=int, default=1)
    parser.add_argument("--save_npy", action="store_true")
    parser.add_argument("--save_vis_interval", type=int, default=1000000)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
