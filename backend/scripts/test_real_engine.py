"""端到端验证真实姿态分析引擎。

用带真人的测试图合成一段“跳跃”视频：整帧按正弦上下平移（2 次/秒 × 10 秒 = 20 跳），
跑 analyze_jump_rope_real 验证峰值计数是否接近 20。
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np

from app.scoring.engine import analyze_jump_rope_real

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
IMG_PATH = MODELS_DIR / "test_pose.jpg"
VIDEO_PATH = MODELS_DIR / "test_jump.mp4"

JUMP_HZ = 2.0
DURATION = 10.0
FPS = 24
AMPLITUDE_RATIO = 0.03  # 振幅 = 3% 画面高


def build_video() -> None:
    img = cv2.imread(str(IMG_PATH))
    assert img is not None, f"cannot read {IMG_PATH}"
    h, w = img.shape[:2]
    amp = int(h * AMPLITUDE_RATIO)

    writer = cv2.VideoWriter(
        str(VIDEO_PATH), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (w, h)
    )
    total = int(DURATION * FPS)
    for i in range(total):
        t = i / FPS
        # 跳跃是半波：地面停留 + 腾空，用 |sin| 更接近真实髋部轨迹
        offset = -int(amp * abs(math.sin(math.pi * JUMP_HZ * t)))
        M = np.float32([[1, 0, 0], [0, 1, offset]])
        frame = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
        writer.write(frame)
    writer.release()
    print(f"built {VIDEO_PATH} ({total} frames, expect ~{int(JUMP_HZ * DURATION)} jumps)")


def main() -> None:
    build_video()
    result = analyze_jump_rope_real(VIDEO_PATH, max_duration_sec=120)
    print("jump_count      :", result.jump_count)
    print("speed_per_min   :", result.speed_per_min)
    print("fancy_count     :", result.fancy_count)
    print("fancy_duration  :", result.fancy_duration_sec)
    print("duration_sec    :", result.duration_sec)
    print("score           :", result.score)
    print("meta            :", result.meta)

    expected = JUMP_HZ * DURATION
    assert abs(result.jump_count - expected) <= expected * 0.2, (
        f"jump_count {result.jump_count} deviates too much from expected {expected}"
    )
    print("PASS: count within 20% of expected")


if __name__ == "__main__":
    main()
