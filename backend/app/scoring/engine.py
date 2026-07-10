"""跳绳视频 AI 分析引擎（真实姿态估计版）。

JUMP_AI_MODE=real（默认）：MediaPipe Pose 逐帧提取人体骨架，
通过髋部垂直位移峰值检测计数，识别交叉跳（手腕交叉）与双摇（异常高跳）。

JUMP_AI_MODE=mock：保留启发式模拟，仅供无摄像素材的本地联调。
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# 姿态采样目标帧率（越高越准，越低越快）
TARGET_SAMPLE_FPS = float(os.getenv("POSE_SAMPLE_FPS", "24"))
# MediaPipe 模型复杂度：0=lite（最快）/ 1=full（平衡）/ 2=heavy（最准）
POSE_MODEL_COMPLEXITY = int(os.getenv("POSE_MODEL_COMPLEXITY", "1"))
# 至少需要多少比例的采样帧检测到人体
MIN_POSE_COVERAGE = 0.4
MIN_POSE_FRAMES = 20

# MediaPipe PoseLandmarker 模型（Tasks API）
_MODEL_VARIANTS = {0: "lite", 1: "full", 2: "heavy"}
_MODEL_URL_TEMPLATE = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_{variant}/float16/latest/pose_landmarker_{variant}.task"
)
MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "models"

# MediaPipe Pose landmark 索引
LEFT_SHOULDER, RIGHT_SHOULDER = 11, 12
LEFT_WRIST, RIGHT_WRIST = 15, 16
LEFT_HIP, RIGHT_HIP = 23, 24
LEFT_ANKLE, RIGHT_ANKLE = 27, 28


def _ensure_pose_model() -> Path:
    """返回姿态模型路径；不存在时自动从官方源下载。"""
    custom = os.getenv("POSE_MODEL_PATH", "").strip()
    if custom:
        path = Path(custom)
        if not path.exists():
            raise RuntimeError(f"POSE_MODEL_PATH 不存在: {path}")
        return path

    variant = _MODEL_VARIANTS.get(POSE_MODEL_COMPLEXITY, "full")
    path = MODELS_DIR / f"pose_landmarker_{variant}.task"
    if path.exists():
        return path

    import urllib.request

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    url = _MODEL_URL_TEMPLATE.format(variant=variant)
    logger.info("downloading pose model: %s", url)
    tmp = path.with_suffix(".task.tmp")
    urllib.request.urlretrieve(url, tmp)  # noqa: S310
    tmp.replace(path)
    return path


@dataclass
class JumpAnalysis:
    jump_count: int
    speed_per_min: float
    fancy_count: int
    fancy_duration_sec: float
    duration_sec: float
    score: float
    fancy_segments: list[dict] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @property
    def total(self) -> float:
        return self.score


def probe_duration_sec(video_path: Path) -> float:
    """用 ffprobe 读取时长；失败则返回 0。"""
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return max(0.0, float(proc.stdout.strip()))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    return 0.0


# ──────────────────────────────────────────────────────────────
# 真实分析：MediaPipe Pose + 峰值计数
# ──────────────────────────────────────────────────────────────


@dataclass
class _FrameSample:
    t: float
    hip_y: float
    body_h: float
    crossed: bool


def _lm_visible(lm, idx: int, threshold: float = 0.5) -> bool:
    """Tasks API 的 visibility 可能全为 0（未填充），此时视为可见。"""
    vis = getattr(lm[idx], "visibility", None)
    if vis is None or vis <= 0.0:
        return True
    return vis >= threshold


def _extract_pose_series(
    video_path: Path, *, max_duration_sec: float
) -> tuple[list[_FrameSample], dict]:
    """逐帧跑 MediaPipe PoseLandmarker（Tasks API / VIDEO 模式），
    输出髋部高度时间序列与元信息。"""
    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python as mp_tasks
    from mediapipe.tasks.python import vision

    model_path = _ensure_pose_model()

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    if not (1.0 < fps <= 120.0):
        fps = 30.0
    step = max(1, round(fps / TARGET_SAMPLE_FPS))
    sample_fps = fps / step

    samples: list[_FrameSample] = []
    sampled_frames = 0
    last_t = 0.0

    options = vision.PoseLandmarkerOptions(
        base_options=mp_tasks.BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    landmarker = vision.PoseLandmarker.create_from_options(options)
    try:
        frame_idx = 0
        prev_ts_ms = -1
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            t = frame_idx / fps
            if t > max_duration_sec + 0.5:
                break
            if frame_idx % step != 0:
                frame_idx += 1
                continue
            frame_idx += 1
            sampled_frames += 1
            last_t = t

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            ts_ms = int(round(t * 1000))
            if ts_ms <= prev_ts_ms:  # VIDEO 模式要求时间戳严格递增
                ts_ms = prev_ts_ms + 1
            prev_ts_ms = ts_ms

            result = landmarker.detect_for_video(mp_image, ts_ms)
            if not result.pose_landmarks:
                continue
            lm = result.pose_landmarks[0]

            if not (_lm_visible(lm, LEFT_HIP) and _lm_visible(lm, RIGHT_HIP)):
                continue
            hip_y = (lm[LEFT_HIP].y + lm[RIGHT_HIP].y) / 2.0

            # 人体尺度：肩到踝的垂直跨度（用于阈值自适应）
            body_h = 0.0
            if _lm_visible(lm, LEFT_SHOULDER) and _lm_visible(lm, RIGHT_SHOULDER):
                shoulder_y = (lm[LEFT_SHOULDER].y + lm[RIGHT_SHOULDER].y) / 2.0
                if _lm_visible(lm, LEFT_ANKLE) and _lm_visible(lm, RIGHT_ANKLE):
                    ankle_y = (lm[LEFT_ANKLE].y + lm[RIGHT_ANKLE].y) / 2.0
                    body_h = abs(ankle_y - shoulder_y)

            # 交叉跳：手腕左右顺序与肩膀相反（对镜像/朝向鲁棒）
            crossed = False
            if (
                _lm_visible(lm, LEFT_WRIST)
                and _lm_visible(lm, RIGHT_WRIST)
                and _lm_visible(lm, LEFT_SHOULDER)
                and _lm_visible(lm, RIGHT_SHOULDER)
            ):
                wrist_dx = lm[LEFT_WRIST].x - lm[RIGHT_WRIST].x
                shoulder_dx = lm[LEFT_SHOULDER].x - lm[RIGHT_SHOULDER].x
                crossed = wrist_dx * shoulder_dx < 0 and abs(wrist_dx) > 0.02

            samples.append(_FrameSample(t=t, hip_y=hip_y, body_h=body_h, crossed=crossed))
    finally:
        landmarker.close()
        cap.release()

    meta = {
        "video_fps": round(fps, 2),
        "sample_fps": round(sample_fps, 2),
        "sampled_frames": sampled_frames,
        "pose_frames": len(samples),
        "duration_sec": round(last_t, 2),
        "model": model_path.name,
    }
    return samples, meta


def _detect_jumps(samples: list[_FrameSample], sample_fps: float):
    """髋部垂直位移峰值检测：返回 (峰值时间数组, 峰值突出度数组)。"""
    import numpy as np
    from scipy.signal import find_peaks, medfilt

    t = np.array([s.t for s in samples])
    hip = np.array([s.hip_y for s in samples])

    # 基线（人整体在画面中移动/镜头晃动）：约 2 秒的滑动中值
    kernel = int(sample_fps * 2)
    kernel = max(5, kernel | 1)  # 奇数
    if kernel >= len(hip):
        kernel = max(3, (len(hip) - 1) | 1)
    baseline = medfilt(hip, kernel_size=kernel)

    # 图像坐标 y 向下为正，跳起时 hip_y 变小 → 反转成向上为正
    osc = baseline - hip

    # 轻度平滑去抖
    if len(osc) >= 3:
        osc = np.convolve(osc, np.ones(3) / 3.0, mode="same")

    body_h = float(np.median([s.body_h for s in samples if s.body_h > 0]) or 0.5)
    # 突出度阈值：信号自适应 + 人体尺度下限（跳绳小跳约为身高的 2%+）
    std = float(np.std(osc))
    prominence = max(0.012 * body_h, 0.45 * std)
    prominence = max(prominence, 0.005)

    # 相邻跳最小间隔：最快按 4.5 跳/秒
    distance = max(1, int(0.22 * sample_fps))

    peaks, props = find_peaks(osc, prominence=prominence, distance=distance)
    return t[peaks], props.get("prominences", np.array([])), body_h


def _group_segments(times: list[float], *, gap: float, min_len: float, label: str, pad: float = 0.15):
    """把离散时间点聚成片段。"""
    segments: list[dict] = []
    if not times:
        return segments
    start = prev = times[0]
    for x in times[1:] + [None]:  # type: ignore[list-item]
        if x is not None and x - prev <= gap:
            prev = x
            continue
        seg_start = max(0.0, start - pad)
        seg_end = prev + pad
        if seg_end - seg_start >= min_len:
            segments.append(
                {
                    "start_sec": round(seg_start, 1),
                    "end_sec": round(seg_end, 1),
                    "label": label,
                }
            )
        if x is not None:
            start = prev = x
    return segments


def analyze_jump_rope_real(video_path: Path, *, max_duration_sec: float = 120.0) -> JumpAnalysis:
    """MediaPipe Pose 姿态估计 + 峰值计数。"""
    import numpy as np

    samples, meta = _extract_pose_series(video_path, max_duration_sec=max_duration_sec)
    duration = meta["duration_sec"] or probe_duration_sec(video_path)

    coverage = len(samples) / max(1, meta["sampled_frames"])
    if len(samples) < MIN_POSE_FRAMES or coverage < MIN_POSE_COVERAGE:
        raise RuntimeError(
            f"未能稳定检测到人体姿态（检出率 {coverage:.0%}），"
            "请确保全身入镜、光线充足、镜头稳定"
        )

    peak_times, prominences, body_h = _detect_jumps(samples, meta["sample_fps"])
    jump_count = int(len(peak_times))

    # 速度：用首末跳的活动区间，比全视频时长更贴近实际
    if jump_count >= 2:
        intervals = np.diff(peak_times)
        median_interval = float(np.median(intervals))
        active = float(peak_times[-1] - peak_times[0]) + median_interval
        speed = round(jump_count / active * 60.0, 1) if active > 0 else 0.0
    elif jump_count == 1 and duration > 0:
        speed = round(60.0 / duration, 1)
        median_interval = 0.0
        intervals = np.array([])
    else:
        speed = 0.0
        median_interval = 0.0
        intervals = np.array([])

    # 双摇：跳跃高度显著高于中位（转两圈需要更高滞空）
    double_times: list[float] = []
    if jump_count >= 4 and len(prominences) == jump_count:
        median_prom = float(np.median(prominences))
        if median_prom > 0:
            double_times = [
                float(pt)
                for pt, prom in zip(peak_times, prominences)
                if prom > 1.7 * median_prom
            ]

    # 交叉跳：手腕交叉的连续帧片段
    crossed_times = [s.t for s in samples if s.crossed]
    cross_segments = _group_segments(
        crossed_times, gap=0.35, min_len=0.25, label="交叉跳"
    )
    double_segments = _group_segments(
        double_times, gap=1.5, min_len=0.2, label="双摇", pad=0.2
    )

    fancy_segments = sorted(
        cross_segments + double_segments, key=lambda s: s["start_sec"]
    )
    for i, seg in enumerate(fancy_segments, start=1):
        seg["index"] = i
    fancy_count = len(fancy_segments)
    fancy_duration = round(
        sum(s["end_sec"] - s["start_sec"] for s in fancy_segments), 1
    )

    # 综合分：速度 55 + 稳定性 25 + 花式 20，封顶 100
    if jump_count == 0:
        score = 0.0
    else:
        speed_score = min(1.0, speed / 160.0) * 55.0
        consistency = 0.0
        if len(intervals) >= 3 and median_interval > 0:
            cv = float(np.std(intervals) / np.mean(intervals))
            consistency = max(0.0, 1.0 - cv) * 25.0
        fancy_bonus = min(20.0, fancy_count * 4.0 + fancy_duration * 0.5)
        score = round(min(100.0, speed_score + consistency + fancy_bonus), 1)

    meta.update(
        {
            "mode": "real",
            "engine": "mediapipe-pose",
            "pose_coverage": round(coverage, 2),
            "body_height_norm": round(body_h, 3),
            "median_jump_interval_sec": round(median_interval, 3),
            "double_under_jumps": len(double_times),
        }
    )

    return JumpAnalysis(
        jump_count=jump_count,
        speed_per_min=speed,
        fancy_count=fancy_count,
        fancy_duration_sec=fancy_duration,
        duration_sec=round(float(duration), 1),
        score=score,
        fancy_segments=fancy_segments,
        meta=meta,
    )


# ──────────────────────────────────────────────────────────────
# mock：仅供无真实素材时联调
# ──────────────────────────────────────────────────────────────


def _stable_seed(path: Path) -> int:
    h = hashlib.sha256()
    h.update(path.name.encode("utf-8"))
    try:
        h.update(str(path.stat().st_size).encode("ascii"))
    except OSError:
        pass
    return int(h.hexdigest()[:8], 16)


def path_size_mb(path: Path) -> float:
    return path.stat().st_size / (1024 * 1024)


def analyze_jump_rope_mock(video_path: Path, *, max_duration_sec: float = 120.0) -> JumpAnalysis:
    """启发式模拟：稳定可复现，覆盖次数/速度/花式指标。"""
    duration = probe_duration_sec(video_path)
    if duration <= 0:
        try:
            size_mb = path_size_mb(video_path)
            duration = min(max_duration_sec, max(8.0, size_mb * 4.0))
        except OSError:
            duration = 30.0
    duration = min(duration, max_duration_sec)

    seed = _stable_seed(video_path)
    base_speed = 60 + (seed % 81)
    speed = round(base_speed + math.sin(seed % 17) * 8, 1)
    jump_count = max(1, int(round(speed * duration / 60.0)))

    fancy_count = (seed // 11) % 6
    fancy_duration = 0.0
    segments: list[dict] = []
    if fancy_count > 0 and duration > 5:
        budget = min(duration * 0.25, fancy_count * 4.0)
        per = budget / fancy_count
        fancy_duration = round(budget, 1)
        cursor = duration * 0.15
        for i in range(fancy_count):
            start = round(min(cursor, duration - 1.0), 1)
            end = round(min(start + per, duration), 1)
            segments.append(
                {
                    "index": i + 1,
                    "start_sec": start,
                    "end_sec": end,
                    "label": ["交叉跳", "双摇", "侧摆", "高抬腿", "编花"][i % 5],
                }
            )
            cursor = end + duration * 0.08

    density = min(1.0, speed / 140.0)
    fancy_bonus = min(20.0, fancy_count * 3.5 + fancy_duration * 0.5)
    score = round(min(100.0, 55 + density * 25 + fancy_bonus), 1)

    return JumpAnalysis(
        jump_count=jump_count,
        speed_per_min=speed,
        fancy_count=fancy_count,
        fancy_duration_sec=fancy_duration,
        duration_sec=round(duration, 1),
        score=score,
        fancy_segments=segments,
        meta={"mode": "mock", "seed": seed},
    )


def analyze_jump_rope(
    video_path: Path, *, mode: str = "real", max_duration_sec: float = 120.0
) -> JumpAnalysis:
    if mode == "mock":
        return analyze_jump_rope_mock(video_path, max_duration_sec=max_duration_sec)
    return analyze_jump_rope_real(video_path, max_duration_sec=max_duration_sec)
