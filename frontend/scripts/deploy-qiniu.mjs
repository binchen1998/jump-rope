import fs from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';
import { build } from 'vite';
import {
  createViteBuildProgressPlugin,
  logDirSummary,
  syncLog,
} from './vite-build-progress.mjs';

import {
  loadBackendEnv,
  collectCodeAssetTargets,
  uploadTargetsInParallel,
  createQiniuUploadToken,
  getRequiredEnv,
  getZone,
  dryRun,
  projectRoot,
  publishStagingToLiveDist,
  partitionHtmlTargets,
  stagingDistDir,
  distDir,
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

  syncLog(`[deploy] building with asset base: ${assetBase}`);
  syncLog('[deploy] vite: reportCompressedSize=false; copyPublicDir=false（大体积 public 走 deploy-assets/CDN）');
  syncLog('[deploy] 构建写入 dist-next/，不删正在托管的 dist/；JS 传完后再切 HTML');
  await logDirSummary('deploy', path.join(projectRoot, 'public'));
  await logDirSummary('deploy', distDir);
  const clearStarted = Date.now();
  await fs.rm(stagingDistDir, { recursive: true, force: true });
  syncLog(`[deploy] cleared dist-next/ in ${((Date.now() - clearStarted) / 1000).toFixed(1)}s`);
  const buildStarted = Date.now();
  await build({
    root: projectRoot,
    base: assetBase,
    logLevel: 'info',
    plugins: [createViteBuildProgressPlugin('deploy')],
    build: {
      outDir: 'dist-next',
      reportCompressedSize: false,
      sourcemap: false,
      copyPublicDir: false,
      emptyOutDir: true,
      watch: null,
    },
  });
  syncLog(`[deploy] vite build finished in ${((Date.now() - buildStarted) / 1000).toFixed(1)}s`);

  const stagingAssetsDir = path.join(stagingDistDir, 'assets');
  const uploadTargets = await collectCodeAssetTargets(prefix, { assetsDir: stagingAssetsDir });
  if (uploadTargets.length === 0) {
    throw new Error(`No build assets found in ${stagingAssetsDir}`);
  }

  const { assetTargets, htmlTargets } = partitionHtmlTargets(uploadTargets);
  console.log(
    `[deploy] found ${uploadTargets.length} files to upload (${assetTargets.length} js/css, ${htmlTargets.length} html last)`,
  );

  if (dryRun) {
    console.log('[deploy] dry-run mode enabled, skipping Qiniu upload');
    for (const target of [...assetTargets, ...htmlTargets]) {
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

  const uploadOptions = { uploadToken, config, mac, bucket };
  if (assetTargets.length) {
    console.log(`[deploy] uploading js/css first, concurrency: ${DEFAULT_UPLOAD_CONCURRENCY}`);
    await uploadTargetsInParallel(assetTargets, uploadOptions, { label: 'deploy' });
  }
  console.log('[deploy] js/css uploaded; publishing HTML to live dist/ last');
  const published = await publishStagingToLiveDist(stagingDistDir, distDir);
  console.log(`[deploy] live dist updated: ${published.otherFiles} assets, ${published.htmlFiles} html`);
  if (htmlTargets.length) {
    console.log(`[deploy] uploading html last, concurrency: ${DEFAULT_UPLOAD_CONCURRENCY}`);
    await uploadTargetsInParallel(htmlTargets, uploadOptions, { label: 'deploy' });
  }
  await fs.rm(stagingDistDir, { recursive: true, force: true });

  console.log('[deploy] upload completed successfully');
  console.log(`[deploy] dist/*.html now references CDN: ${assetBase}assets/...`);
  console.log('[deploy] 本地若要回到本地路径，运行 `npm run build`（默认 base=/）覆盖 dist 即可。');
}

main().catch((error) => {
  console.error('[deploy] failed:', error.message);
  process.exitCode = 1;
});
