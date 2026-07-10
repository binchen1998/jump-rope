import process from 'node:process';
import { build } from 'vite';

import {
  loadBackendEnv,
  collectCodeAssetTargets,
  uploadTargetsInParallel,
  createQiniuUploadToken,
  getRequiredEnv,
  getZone,
  dryRun,
  projectRoot,
  assetsDir,
  joinUrl,
  normalizePrefix,
  DEFAULT_CDN_BASE,
  DEFAULT_PREFIX,
  DEFAULT_UPLOAD_CONCURRENCY,
} from './qiniu-deploy-shared.mjs';

import qiniu from 'qiniu';

async function main() {
  await loadBackendEnv();

  const cdnBase = (process.env.QINIU_CDN_DOMAIN || DEFAULT_CDN_BASE).trim();
  const prefix = normalizePrefix(
    process.env.QINIU_FRONTEND_PREFIX || process.env.QINIU_DEPLOY_PREFIX,
  );
  const assetBase = joinUrl(cdnBase, prefix);

  console.log(`[deploy] building with asset base: ${assetBase}`);
  await build({
    root: projectRoot,
    base: assetBase,
  });

  const uploadTargets = await collectCodeAssetTargets(prefix);
  if (uploadTargets.length === 0) {
    throw new Error(`No build assets found in ${assetsDir}`);
  }

  console.log(`[deploy] found ${uploadTargets.length} code asset files to upload`);

  if (dryRun) {
    console.log('[deploy] dry-run mode enabled, skipping Qiniu upload');
    for (const target of uploadTargets) {
      console.log(`[deploy] would upload: ${target.remoteKey}`);
    }
    return;
  }

  const accessKey = getRequiredEnv('QINIU_ACCESS_KEY');
  const secretKey = getRequiredEnv('QINIU_SECRET_KEY');
  const bucket = getRequiredEnv('QINIU_BUCKET');
  const region = process.env.QINIU_REGION || 'z0';

  const mac = new qiniu.auth.digest.Mac(accessKey, secretKey);
  const uploadToken = createQiniuUploadToken(mac, bucket);
  const config = new qiniu.conf.Config();
  config.zone = getZone(region);
  config.useHttpsDomain = true;
  config.useCdnDomain = true;

  console.log(`[deploy] uploading with max concurrency: ${DEFAULT_UPLOAD_CONCURRENCY}`);
  await uploadTargetsInParallel(uploadTargets, {
    uploadToken,
    config,
    mac,
    bucket,
  }, { label: 'deploy' });

  console.log('[deploy] upload completed successfully');
  console.log(`[deploy] dist/*.html now references CDN: ${assetBase}assets/...`);
  console.log('[deploy] 本地若要回到本地路径，运行 `npm run build`（默认 base=/）覆盖 dist 即可。');
}

main().catch((error) => {
  console.error('[deploy] failed:', error.message);
  process.exitCode = 1;
});
