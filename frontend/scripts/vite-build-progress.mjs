/**
 * Vite 构建阶段日志：卡在 modules transformed 之后时，用心跳定位慢在哪一步。
 * 用 writeSync 直写 stdout，避免非 TTY / 管道缓冲导致日志迟迟不出现。
 */
import fs from 'node:fs/promises';
import { writeSync } from 'node:fs';
import path from 'node:path';
import process from 'node:process';

function rssMb() {
  return Math.round(process.memoryUsage().rss / 1024 / 1024);
}

function heapMb() {
  return Math.round(process.memoryUsage().heapUsed / 1024 / 1024);
}

export function syncLog(line) {
  writeSync(1, `${line}\n`);
}

function formatMb(bytes) {
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

/** 统计目录文件数与总大小（用于发现 public 里堆积的 mp3）。 */
export async function summarizeDir(dir) {
  let files = 0;
  let bytes = 0;
  async function walk(current) {
    let entries;
    try {
      entries = await fs.readdir(current, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) {
        await walk(full);
      } else if (entry.isFile()) {
        files += 1;
        try {
          bytes += (await fs.stat(full)).size;
        } catch {
          /* ignore */
        }
      }
    }
  }
  await walk(dir);
  return { files, bytes };
}

/**
 * @param {string} label
 * @param {string} dir
 */
export async function logDirSummary(label, dir) {
  const exists = await fs.access(dir).then(() => true).catch(() => false);
  if (!exists) {
    syncLog(`[${label}] ${dir} 不存在`);
    return { files: 0, bytes: 0 };
  }
  const t0 = Date.now();
  const { files, bytes } = await summarizeDir(dir);
  syncLog(
    `[${label}] ${dir} → ${files} files / ${formatMb(bytes)} (scan ${Date.now() - t0}ms)`,
  );
  return { files, bytes };
}

/**
 * @param {string} label
 * @param {{ heartbeatMs?: number }} [options]
 */
export function createViteBuildProgressPlugin(label = 'vite', options = {}) {
  const heartbeatMs = options.heartbeatMs ?? 10_000;
  const t0 = Date.now();
  let lastPhase = 'init';
  let heartbeat = null;

  const mark = (phase, detail = '') => {
    lastPhase = phase;
    const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
    const extra = detail ? ` ${detail}` : '';
    syncLog(
      `[${label}] +${elapsed}s rss=${rssMb()}MB heap=${heapMb()}MB · ${phase}${extra}`,
    );
  };

  const startHeartbeat = () => {
    stopHeartbeat();
    heartbeat = setInterval(() => {
      const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
      syncLog(
        `[${label}] +${elapsed}s rss=${rssMb()}MB heap=${heapMb()}MB · …仍在「${lastPhase}」(未进入下一阶段，可能在 minify/写盘/gzip)`,
      );
    }, heartbeatMs);
    // 不要阻碍进程退出
    if (typeof heartbeat.unref === 'function') heartbeat.unref();
  };

  const stopHeartbeat = () => {
    if (heartbeat) {
      clearInterval(heartbeat);
      heartbeat = null;
    }
  };

  return {
    name: 'vite-build-progress',
    buildStart() {
      mark('buildStart', '(开始 rollup 解析/转换)');
      startHeartbeat();
    },
    buildEnd(err) {
      if (err) {
        mark('buildEnd', `(rollup 失败: ${err.message || err})`);
      } else {
        mark(
          'buildEnd',
          '(rollup 结束 → Vite 将 emptyDir(dist) 并可能 copyPublicDir；public 很大时会在此卡住)',
        );
      }
    },
    renderStart() {
      mark('renderStart', '(emptyDir/copyPublic 已结束，开始 renderChunk / minify)');
    },
    generateBundle(_options, bundle) {
      const n = bundle ? Object.keys(bundle).length : 0;
      mark('generateBundle', `(产物 ${n} 个，即将写盘)`);
    },
    writeBundle(_options, bundle) {
      const n = bundle ? Object.keys(bundle).length : 0;
      mark('writeBundle', `(已写出 ${n} 个文件)`);
    },
    closeBundle() {
      mark('closeBundle', '(构建收尾完成)');
      stopHeartbeat();
    },
  };
}
