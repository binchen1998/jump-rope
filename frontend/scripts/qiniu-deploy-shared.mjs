import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

import qiniu from 'qiniu';

export const DEFAULT_UPLOAD_CONCURRENCY = 8;

export function formatFileSize(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export function formatSpeed(bytesPerSec) {
  return `${formatFileSize(bytesPerSec)}/s`;
}

export function formatDuration(seconds) {
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}m${secs}s`;
}

/**
 * @param {object} options
 * @param {string} options.label 日志前缀，如 deploy
 * @param {string} options.remoteKey
 * @param {number} options.fileSize
 * @param {number} [options.workerId]
 * @param {number} [options.index] 1-based
 * @param {number} [options.total]
 */
export function createUploadProgressReporter(options) {
  const {
    label,
    remoteKey,
    fileSize,
    workerId,
    index,
    total,
  } = options;
  const startTime = Date.now();
  let lastReportTime = 0;
  let lastReportPct = -1;
  let finished = false;

  const workerTag = workerId != null ? ` worker-${workerId}` : '';
  const counter = index != null && total != null ? ` [${index}/${total}]` : '';
  const prefix = `[${label}]${counter}${workerTag}`;

  function logProgress(uploadBytes, totalBytes) {
    const totalSize = totalBytes || fileSize || 0;
    const now = Date.now();
    const elapsed = (now - startTime) / 1000;
    const pct = totalSize > 0
      ? Math.min(100, Math.floor((uploadBytes / totalSize) * 100))
      : 100;
    const speed = elapsed > 0 ? uploadBytes / elapsed : 0;
    const done = totalSize > 0 && uploadBytes >= totalSize;
    const suffix = done ? `  done (${formatDuration(elapsed)})` : '';

    if (!done && now - lastReportTime < 400 && pct - lastReportPct < 5) {
      return;
    }
    lastReportTime = now;
    lastReportPct = pct;
    if (done) {
      finished = true;
    }

    console.log(
      `${prefix} ${remoteKey}  ${pct}%  ${formatFileSize(uploadBytes)}/${formatFileSize(totalSize)}  ${formatSpeed(speed)}${suffix}`,
    );
  }

  return {
    start() {
      console.log(`${prefix} start ${remoteKey} (${formatFileSize(fileSize)})`);
    },
    onProgress: logProgress,
    finish() {
      if (!finished) {
        logProgress(fileSize, fileSize);
      }
    },
  };
}

/**
 * 生成上传凭证。insertOnly 必须为 0，否则同名 key 已存在时会返回 HTTP 614（无法覆盖）。
 * @see https://developer.qiniu.com/kodo/1206/put-policy
 */
export function createQiniuUploadToken(mac, bucket) {
  const putPolicy = new qiniu.rs.PutPolicy({
    scope: bucket,
    insertOnly: 0,
  });
  return putPolicy.uploadToken(mac);
}

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
export const projectRoot = path.resolve(__dirname, '..');
export const backendEnvPath = path.resolve(projectRoot, '..', 'backend', '.env');
export const distDir = path.join(projectRoot, 'dist');
/** deploy 构建暂存目录：不碰正在被后端托管的 dist/，避免一开打就「前端尚未构建」。 */
export const stagingDistDir = path.join(projectRoot, 'dist-next');
export const assetsDir = path.join(distDir, 'assets');
export const razAudioPublicDir = path.join(projectRoot, 'public', 'raz-audio');

export const DEFAULT_CDN_BASE = 'https://static1.cxy61.com/';
export const DEFAULT_PREFIX = 'jump-rope';

export const dryRun = process.argv.includes('--dry-run');

export function trimSlashes(value) {
  return value.replace(/^\/+|\/+$/g, '');
}

export function normalizePrefix(value) {
  const trimmed = trimSlashes(value || DEFAULT_PREFIX);
  return trimmed || DEFAULT_PREFIX;
}

export function parseEnvLine(line) {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith('#')) {
    return null;
  }
  const separatorIndex = trimmed.indexOf('=');
  if (separatorIndex <= 0) {
    return null;
  }
  const key = trimmed.slice(0, separatorIndex).trim();
  let value = trimmed.slice(separatorIndex + 1).trim();
  if (
    (value.startsWith('"') && value.endsWith('"'))
    || (value.startsWith("'") && value.endsWith("'"))
  ) {
    value = value.slice(1, -1);
  }
  return [key, value];
}

export async function loadBackendEnv() {
  let content = '';
  try {
    content = await fs.readFile(backendEnvPath, 'utf8');
  } catch (error) {
    if (error && error.code === 'ENOENT') {
      return;
    }
    throw error;
  }

  for (const line of content.split(/\r?\n/)) {
    const parsed = parseEnvLine(line);
    if (!parsed) {
      continue;
    }
    const [key, value] = parsed;
    if (!(key in process.env)) {
      process.env[key] = value;
    }
  }
}

export function joinUrl(base, ...parts) {
  const cleanedBase = base.replace(/\/+$/, '');
  const cleanedParts = parts
    .filter(Boolean)
    .map((part) => trimSlashes(part))
    .filter(Boolean);
  return `${cleanedBase}/${cleanedParts.join('/')}/`;
}

export async function walkFiles(dir) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      return walkFiles(fullPath);
    }
    return [fullPath];
  }));
  return files.flat().sort();
}

export async function pathExists(targetPath) {
  try {
    await fs.access(targetPath);
    return true;
  } catch {
    return false;
  }
}

export function getRequiredEnv(name) {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value;
}

export function getZone(region) {
  const zoneMap = {
    z0: qiniu.zone.Zone_z0,
    z1: qiniu.zone.Zone_z1,
    z2: qiniu.zone.Zone_z2,
    na0: qiniu.zone.Zone_na0,
    as0: qiniu.zone.Zone_as0,
  };
  const normalized = (region || 'z0').toLowerCase();
  return zoneMap[normalized] || qiniu.zone.Zone_z0;
}

function formatQiniuBody(body) {
  if (body == null) return '';
  if (typeof body === 'string') return body.slice(0, 400);
  try {
    return JSON.stringify(body).slice(0, 400);
  } catch {
    return '';
  }
}

/**
 * 删除空间中的对象。不存在时忽略（612）。
 */
export function deleteRemoteObject({ mac, config, bucket, remoteKey }) {
  const bm = new qiniu.rs.BucketManager(mac, config);
  return new Promise((resolve, reject) => {
    bm.delete(bucket, remoteKey, (err, body, info) => {
      if (err) {
        reject(err);
        return;
      }
      if (info.statusCode >= 200 && info.statusCode < 300) {
        resolve();
        return;
      }
      if (info.statusCode === 612) {
        resolve();
        return;
      }
      reject(new Error(
        `Qiniu delete failed for ${remoteKey}: HTTP ${info.statusCode} ${formatQiniuBody(body)}`,
      ));
    });
  });
}

function putFileOnce({ uploadToken, config, localFile, remoteKey, onProgress }) {
  const resumeUploader = new qiniu.resume_up.ResumeUploader(config);
  const putExtra = qiniu.resume_up.PutExtra.create();
  if (onProgress) {
    putExtra.progressCallback = onProgress;
  }

  return new Promise((resolve, reject) => {
    resumeUploader.putFileV2(uploadToken, remoteKey, localFile, putExtra, (err, body, info) => {
      if (err) {
        reject(err);
        return;
      }
      if (info.statusCode >= 200 && info.statusCode < 300) {
        resolve(body);
        return;
      }
      const message = `Qiniu upload failed for ${remoteKey}: HTTP ${info.statusCode} ${formatQiniuBody(body)}`;
      const error = new Error(message);
      error.statusCode = info.statusCode;
      error.rawBody = body;
      reject(error);
    });
  });
}

/**
 * @param {object} params
 * @param {string} params.uploadToken
 * @param {object} params.config qiniu.conf.Config
 * @param {string} params.localFile
 * @param {string} params.remoteKey
 * @param {object} [params.mac] 与 bucket 同时传入时，遇 614 会先删后传
 * @param {string} [params.bucket]
 * @param {object} [params.uploadMeta] 传入后在终端打印上传进度与速度
 * @param {string} params.uploadMeta.label
 * @param {number} [params.uploadMeta.workerId]
 * @param {number} [params.uploadMeta.index] 1-based
 * @param {number} [params.uploadMeta.total]
 */
export async function uploadFile(params) {
  const {
    uploadToken,
    config,
    localFile,
    remoteKey,
    mac,
    bucket,
    uploadMeta,
  } = params;

  const { size: fileSize } = await fs.stat(localFile);
  let progressReporter = null;
  let onProgress = null;

  if (uploadMeta) {
    progressReporter = createUploadProgressReporter({
      ...uploadMeta,
      remoteKey,
      fileSize,
    });
    progressReporter.start();
    onProgress = progressReporter.onProgress;
  }

  async function uploadOnce() {
    await putFileOnce({
      uploadToken,
      config,
      localFile,
      remoteKey,
      onProgress,
    });
    progressReporter?.finish();
  }

  try {
    await uploadOnce();
  } catch (firstError) {
    const code = firstError?.statusCode;
    if (code === 614 && mac && bucket) {
      await deleteRemoteObject({ mac, config, bucket, remoteKey });
      await uploadOnce();
      return;
    }
    throw firstError;
  }
}

/**
 * @param {Array<{ localFile: string, remoteKey: string }>} uploadTargets
 * @param {object} uploadOptions uploadFile 参数（不含 localFile/remoteKey/uploadMeta）
 * @param {object} [options]
 * @param {string} options.label 日志前缀
 * @param {number} [options.maxConcurrency]
 */
export async function uploadTargetsInParallel(uploadTargets, uploadOptions, options) {
  const { label, maxConcurrency = DEFAULT_UPLOAD_CONCURRENCY } = options;
  let nextIndex = 0;
  const total = uploadTargets.length;

  async function worker(workerId) {
    while (true) {
      const currentIndex = nextIndex;
      nextIndex += 1;
      if (currentIndex >= total) return;
      const target = uploadTargets[currentIndex];
      await uploadFile({
        ...uploadOptions,
        localFile: target.localFile,
        remoteKey: target.remoteKey,
        uploadMeta: {
          label,
          workerId,
          index: currentIndex + 1,
          total,
        },
      });
    }
  }

  const workerCount = Math.min(maxConcurrency, total);
  await Promise.all(
    Array.from({ length: workerCount }, (_, index) => worker(index + 1)),
  );
}


export function isHtmlTarget(target) {
  return typeof target?.remoteKey === 'string' && target.remoteKey.toLowerCase().endsWith('.html');
}

export function partitionHtmlTargets(uploadTargets) {
  const assetTargets = [];
  const htmlTargets = [];
  for (const target of uploadTargets) {
    if (isHtmlTarget(target)) htmlTargets.push(target);
    else assetTargets.push(target);
  }
  return { assetTargets, htmlTargets };
}

/**
 * 把暂存构建拷到正在被后端托管的 dist/：先非 HTML，最后才覆盖入口 HTML。
 * 不先删 dist，旧页面在切 HTML 之前一直可访问。
 */
export async function publishStagingToLiveDist(fromDir, toDir) {
  const files = await walkFiles(fromDir);
  const htmlFiles = [];
  const otherFiles = [];
  for (const file of files) {
    if (file.toLowerCase().endsWith('.html')) htmlFiles.push(file);
    else otherFiles.push(file);
  }
  htmlFiles.sort((a, b) => {
    const aIndex = path.basename(a) === 'index.html' ? 1 : 0;
    const bIndex = path.basename(b) === 'index.html' ? 1 : 0;
    return aIndex - bIndex;
  });

  for (const src of [...otherFiles, ...htmlFiles]) {
    const dest = path.join(toDir, path.relative(fromDir, src));
    await fs.mkdir(path.dirname(dest), { recursive: true });
    await fs.copyFile(src, dest);
  }

  return { otherFiles: otherFiles.length, htmlFiles: htmlFiles.length };
}

/** Vite-bundled JS/CSS under dist/assets/ → math/assets/... */
export async function collectCodeAssetTargets(prefix, options = {}) {
  const fromAssetsDir = options.assetsDir || assetsDir;
  const targets = [];
  if (!(await pathExists(fromAssetsDir))) {
    return targets;
  }
  const assetFiles = await walkFiles(fromAssetsDir);
  for (const localFile of assetFiles) {
    const relativePath = path.relative(fromAssetsDir, localFile).split(path.sep).join('/');
    targets.push({
      localFile,
      remoteKey: `${prefix}/assets/${relativePath}`,
    });
  }
  return targets;
}

/** RAZ 英语朗读 mp3：public/raz-audio → math/raz-audio/... */
export async function collectRazAudioTargets(prefix) {
  const targets = [];
  if (!(await pathExists(razAudioPublicDir))) {
    return targets;
  }
  const files = await walkFiles(razAudioPublicDir);
  for (const localFile of files) {
    if (!localFile.toLowerCase().endsWith('.mp3')) {
      continue;
    }
    const relativePath = path.relative(razAudioPublicDir, localFile).split(path.sep).join('/');
    targets.push({
      localFile,
      remoteKey: `${prefix}/raz-audio/${relativePath}`,
    });
  }
  return targets;
}
