# Jump Rope 跳绳

上传跳绳视频 → 后台 AI 分析（次数 / 速度 / 花式）→ 前端每 10 秒轮询 → 发布到广场 / 投稿编辑推荐 / 参加比赛投票。

## 技术栈

- 后端：FastAPI + SQLAlchemy（SQLite / MySQL）
- 前端：Vue 3 + Vite + Tailwind（UI 风格对齐 math）
- Worker：独立进程（转码、打分、比赛结算、七牛 DB 备份）
- 静态：生产环境由 FastAPI 托管 `frontend/dist`；`npm run deploy` 上传到七牛 CDN

## 快速开始

```powershell
.\setup.ps1
.\run-backend.ps1      # :8000
.\run-worker.ps1       # 必须单独开
.\run-frontend.ps1     # :5173，代理 /api → :8000
```

管理员默认：`admin` / `coding61`

## 核心能力

| 能力 | 说明 |
|------|------|
| 上传 | 每天 1 个视频，最长 2 分钟，≤200MB |
| AI 分析 | MediaPipe 姿态估计：总次数、次/分钟、花式次数与时长（默认 `JUMP_AI_MODE=real`） |
| 轮询 | `GET /api/videos/{id}/score`，前端 10 秒一次 |
| 广场 | 发布后进入公开 feed，全站今日上传统计 |
| 编辑推荐 | 用户投稿 → 管理员审核 |
| 比赛 | 投稿参赛、投票、到期自动结算 |
| 双库 | `DB_TYPE=sqlite\|mysql` |
| 部署 | `npm run build` 本地托管；`npm run deploy` 七牛 CDN |
| 备份 | Worker 定时备份 DB 到七牛私有 bucket |

## AI 分析原理（JUMP_AI_MODE=real，默认）

1. **姿态估计**：MediaPipe PoseLandmarker（Tasks API，VIDEO 模式）逐帧提取 33 个人体关键点，采样帧率 `POSE_SAMPLE_FPS`（默认 24）。
2. **计数**：取左右髋部中点的垂直坐标序列，用约 2 秒滑动中值去除镜头/身体整体位移作基线，对"向上位移"信号做峰值检测（scipy `find_peaks`，突出度按人体尺度自适应），峰值数即跳绳次数。
3. **速度**：次数 ÷ 首末跳活动区间 × 60。
4. **花式识别**：
   - 交叉跳：手腕左右顺序与肩膀相反（对镜像/朝向鲁棒）的连续片段；
   - 双摇：跳跃高度显著高于中位（>1.7×）的跳。
5. **综合分**：速度 55 + 节奏稳定性 25（跳跃间隔变异系数）+ 花式 20，封顶 100。
6. 人体检出率低于 40% 时报错提示"全身入镜、光线充足"。

姿态模型（约 9MB）首次分析时自动下载到 `backend/models/`，可用 `POSE_MODEL_COMPLEXITY`（0=lite/1=full/2=heavy）与 `POSE_MODEL_PATH` 调整。`JUMP_AI_MODE=mock` 可切回启发式模拟（无真实素材联调用）。

验证脚本：`cd backend && python scripts/test_real_engine.py`（用真人图合成 2 跳/秒 × 10 秒的跳跃视频，校验计数误差 <20%）。

## 环境变量

见 `backend/.env.example`。切换 MySQL：

```ini
DB_TYPE=mysql
MYSQL_URL=mysql+aiomysql://root:root@localhost:3306/jump_rope
```

然后重新执行 `python -m migrations.0001_init`。

## 生产

```bash
cd frontend && npm run build
cd ../backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
# 另开终端
python -m run_background_workers
```

CDN 场景：`cd frontend && npm run deploy`（读 `backend/.env` 七牛凭证）。
