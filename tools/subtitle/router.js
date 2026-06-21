const express = require('express');
const multer = require('multer');
const fs = require('fs');
const path = require('path');
const { execFile } = require('child_process');
const https = require('https');
const http = require('http');

// Quick HEAD check — resolves with HTTP status code, or 0 on network error
function checkUrlStatus(url, timeoutMs = 8000) {
  return new Promise((resolve) => {
    const mod = url.startsWith('https') ? https : http;
    const req = mod.request(url, { method: 'HEAD', timeout: timeoutMs }, (res) => {
      res.resume();
      resolve(res.statusCode);
    });
    req.on('timeout', () => { req.destroy(); resolve(0); });
    req.on('error', () => resolve(0));
    req.end();
  });
}

const DETECT_SCRIPT = path.join(__dirname, 'detect_watermark.py');
const PYTHON_BIN = process.platform === 'win32' ? 'python' : 'python3';

// Runs the Python watermark detector for a single corner.
// Returns detected { x, y, w, h } or null on failure (falls back to preset).
function detectWatermarkCorner(videoInput, corner, width, height, callback) {
  execFile(
    PYTHON_BIN,
    [DETECT_SCRIPT, videoInput, corner, String(width), String(height)],
    { timeout: 60000 },
    (err, stdout) => {
      if (err) {
        console.warn(`[Detect] Python error (${corner}):`, err.message);
        return callback(null);
      }
      try {
        const result = JSON.parse(stdout.trim());
        if (result.error) {
          console.warn(`[Detect] Detection failed (${corner}):`, result.error);
          return callback(null);
        }
        console.log(`[Detect] Found watermark (${corner}):`, result);
        callback(result);
      } catch (_) {
        callback(null);
      }
    }
  );
}

// Preset fallback coords (percentage-based)
// top-left is wider to cover multi-logo stacks like SOD + IPPA + No.XXXXXX
function presetCoords(corner, width, height) {
  switch (corner) {
    case 'top-left':     return clampDelogo(0, 0, Math.round(width * 0.22), Math.round(height * 0.18), width, height);
    case 'top-right':    return clampDelogo(width - Math.round(width * 0.16), 0, Math.round(width * 0.16), Math.round(height * 0.16), width, height);
    case 'bottom-left':  return clampDelogo(0, height - Math.round(height * 0.16), Math.round(width * 0.16), Math.round(height * 0.16), width, height);
    case 'bottom-right': return clampDelogo(width - Math.round(width * 0.16), height - Math.round(height * 0.16), Math.round(width * 0.16), Math.round(height * 0.16), width, height);
    default: return null;
  }
}

// Auto-detect watermarks in all 4 corners in parallel.
// If detection finds watermarks → remove only those corners precisely.
// If detection finds nothing → fall back to always removing both-top (safe default for JAV videos).
// callback(filterString)
function autoDetectAllCorners(videoInput, width, height, callback) {
  const corners = ['top-left', 'top-right', 'bottom-left', 'bottom-right'];
  const results = {};
  let done = 0;

  function coordsToFilter(coords) {
    const c = clampDelogo(coords.x, coords.y, coords.w, coords.h, width, height);
    return `delogo=x=${c.x}:y=${c.y}:w=${c.w}:h=${c.h}`;
  }

  function bothTopFallback() {
    const l = presetCoords('top-left',  width, height);
    const r = presetCoords('top-right', width, height);
    console.log('[Detect] Nothing detected — falling back to both-top preset');
    return `${coordsToFilter(l)},${coordsToFilter(r)}`;
  }

  // top-left and top-right always get delogoed (preset if not detected)
  // bottom corners only removed if actually detected
  const alwaysCorners = ['top-left', 'top-right'];
  const optionalCorners = ['bottom-left', 'bottom-right'];

  corners.forEach((corner) => {
    detectWatermarkCorner(videoInput, corner, width, height, (detected) => {
      results[corner] = detected; // null if not detected
      if (++done === corners.length) {
        const filters = [];

        alwaysCorners.forEach((c) => {
          const coords = results[c] || presetCoords(c, width, height);
          filters.push(coordsToFilter(coords));
          console.log(`[Detect] ${c}: ${results[c] ? 'precise coords' : 'preset fallback'}`);
        });

        optionalCorners.forEach((c) => {
          if (results[c]) {
            filters.push(coordsToFilter(results[c]));
            console.log(`[Detect] ${c}: detected, removing`);
          }
        });

        callback(filters.join(','));
      }
    });
  });
}

// Resolves delogo filter string.
// - No delogo param → auto-detect all 4 corners
// - preset → auto-detect that specific corner(s), fallback to preset size if detection fails
// - custom coords → use as-is
function resolveDelogoFilter(delogoStr, videoInput, width, height, callback) {
  function coordsToFilter(coords) {
    const c = clampDelogo(coords.x, coords.y, coords.w, coords.h, width, height);
    return `delogo=x=${c.x}:y=${c.y}:w=${c.w}:h=${c.h}`;
  }

  // No param = fully automatic
  if (!delogoStr) {
    return autoDetectAllCorners(videoInput, width, height, callback);
  }

  let d;
  try { d = JSON.parse(delogoStr); } catch (_) { return autoDetectAllCorners(videoInput, width, height, callback); }

  if (d.preset === 'both-top') {
    let done = 0;
    let leftCoords = null;
    let rightCoords = null;
    function finish() {
      if (++done < 2) return;
      const l = leftCoords  || presetCoords('top-left',  width, height);
      const r = rightCoords || presetCoords('top-right', width, height);
      callback(`${coordsToFilter(l)},${coordsToFilter(r)}`);
    }
    detectWatermarkCorner(videoInput, 'top-left',  width, height, (c) => { leftCoords  = c; finish(); });
    detectWatermarkCorner(videoInput, 'top-right', width, height, (c) => { rightCoords = c; finish(); });

  } else if (d.preset && d.preset !== 'custom') {
    detectWatermarkCorner(videoInput, d.preset, width, height, (detected) => {
      const coords = detected || presetCoords(d.preset, width, height);
      callback(coords ? coordsToFilter(coords) : '');
    });

  } else {
    // Custom coords — use as-is, no detection
    callback(buildDelogoFilter(delogoStr, width, height));
  }
}

const router = express.Router();

const UPLOAD_DIR = path.join(__dirname, 'uploads');
const OUTPUT_DIR = path.join(__dirname, 'output');
const LOGO_PATH = path.join(__dirname, 'AI JAV_logotype_white.png');
const DB_PATH = path.join(__dirname, 'db.json');
if (!fs.existsSync(UPLOAD_DIR)) fs.mkdirSync(UPLOAD_DIR, { recursive: true });
if (!fs.existsSync(OUTPUT_DIR)) fs.mkdirSync(OUTPUT_DIR, { recursive: true });

// In-memory job store: jobId -> { status, url, filename, error, created }
const jobs = new Map();

// Simple JSON DB for metadata
function loadDB() {
  try { return JSON.parse(fs.readFileSync(DB_PATH, 'utf8')); } catch (_) { return {}; }
}
function saveDB(db) {
  fs.writeFileSync(DB_PATH, JSON.stringify(db, null, 2));
}
function saveMeta(filename, meta) {
  const db = loadDB();
  db[filename] = { ...meta, created: Date.now() };
  saveDB(db);
}

const upload = multer({
  storage: multer.diskStorage({
    destination: (req, file, cb) => cb(null, UPLOAD_DIR),
    filename: (req, file, cb) => {
      const ext = path.extname(file.originalname);
      cb(null, `${Date.now()}_${Math.random().toString(36).slice(2, 8)}${ext}`);
    },
  }),
  limits: { fileSize: 4 * 1024 * 1024 * 1024 }, // 4GB
});

function timeToSec(t) {
  const parts = t.split(':').map(Number);
  return parts[0] * 3600 + parts[1] * 60 + (parts[2] || 0);
}

function calcDuration(start, end) {
  const secs = timeToSec(end) - timeToSec(start);
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
}

function escapeSubPath(p) {
  return p.replace(/\\/g, '/').replace(/:/g, '\\:').replace(/'/g, "\\\\'");
}

function clampDelogo(x, y, w, h, width, height) {
  // delogo filter has a default band=1 that extends 1px beyond the specified area for interpolation.
  // We must keep x >= 1, y >= 1, x+w <= width-2, y+h <= height-2 to avoid "outside of frame" error.
  const band = 2; // margin for delogo band
  x = Math.max(band, Math.min(x, width - band - 1));
  y = Math.max(band, Math.min(y, height - band - 1));
  w = Math.min(w, width - x - band);
  h = Math.min(h, height - y - band);
  return { x, y, w, h };
}

function buildDelogoFilter(delogoStr, width, height) {
  if (!delogoStr) return '';
  try {
    const d = JSON.parse(delogoStr);
    if (d.preset === 'both-top') {
      // Left watermark: ~16% width, ~14% height
      const l = clampDelogo(0, 0, Math.round(width * 0.16), Math.round(height * 0.14), width, height);
      // Right watermark: ~16% width, ~16% height
      const rw = Math.round(width * 0.16);
      const rh = Math.round(height * 0.16);
      const r = clampDelogo(width - rw, 0, rw, rh, width, height);
      return `delogo=x=${l.x}:y=${l.y}:w=${l.w}:h=${l.h},delogo=x=${r.x}:y=${r.y}:w=${r.w}:h=${r.h}`;
    }
    let x, y, w, h;
    if (d.preset) {
      w = Math.round(width * 0.14);
      h = Math.round(height * 0.12);
      switch (d.preset) {
        case 'top-left':     x = 0; y = 0; break;
        case 'top-right':    x = width - w; y = 0; break;
        case 'bottom-left':  x = 0; y = height - h; break;
        case 'bottom-right': x = width - w; y = height - h; break;
        default: return '';
      }
    } else {
      x = parseInt(d.x) || 0;
      y = parseInt(d.y) || 0;
      w = parseInt(d.w) || 200;
      h = parseInt(d.h) || 36;
    }
    const c = clampDelogo(x, y, w, h, width, height);
    return `delogo=x=${c.x}:y=${c.y}:w=${c.w}:h=${c.h}`;
  } catch (_) {
    return '';
  }
}

// Logo filter: loop PNG indefinitely so T increments, then geq controls alpha
// visible 1s every 5s via lt(mod(T,5),1)
function buildLogoFilter(logoScale) {
  return `[1:v]loop=loop=-1:size=1:start=0,scale=${logoScale}:-1,format=rgba,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='alpha(X,Y)*0.3*lt(mod(T,5),1)'[logo]`;
}

// Bouncing overlay (DVD screensaver style) — no enable needed, alpha controlled in logo filter
function buildBounceOverlay() {
  const speedX = 80;
  const speedY = 60;
  const x = `abs(mod(t*${speedX}\\,2*(W-w))-(W-w))`;
  const y = `abs(mod(t*${speedY}\\,2*(H-h))-(H-h))`;
  return `overlay=x='${x}':y='${y}'`;
}

function probeResolution(inputPath, callback) {
  execFile('ffprobe', [
    '-v', 'warning',
    '-analyzeduration', '20000000',
    '-probesize', '20000000',
    '-select_streams', 'v:0',
    '-show_entries', 'stream=width,height',
    '-of', 'csv=p=0',
    inputPath,
  ], { timeout: 60000 }, (_err, stdout, stderr) => {
    // Always try to parse stdout first — ffprobe may output resolution even on non-zero exit
    const line = (stdout || '').trim();
    if (line) {
      const [w, h] = line.split(',').map(Number);
      if (w && h) {
        console.log(`[Probe] Detected resolution: ${w}x${h}`);
        return callback(w, h);
      }
    }
    // Fallback: parse from stderr (ffprobe prints stream info there)
    const match = (stderr || '').match(/(\d{3,4})x(\d{3,4})/);
    if (match) {
      const w = parseInt(match[1]);
      const h = parseInt(match[2]);
      console.log(`[Probe] Resolution from stderr fallback: ${w}x${h}`);
      return callback(w, h);
    }
    console.warn('[Probe] Could not detect resolution, using 1280x720 fallback');
    callback(1280, 720);
  });
}

function downloadFile(url, dest, callback) {
  const mod = url.startsWith('https') ? https : http;
  const file = fs.createWriteStream(dest);
  let called = false;
  const done = (err) => { if (called) return; called = true; callback(err); };
  mod.get(url, (res) => {
    if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
      file.close();
      fs.unlinkSync(dest);
      return downloadFile(res.headers.location, dest, callback);
    }
    if (res.statusCode !== 200) {
      file.close();
      fs.unlinkSync(dest);
      return done(new Error(`下载失败，状态码: ${res.statusCode}`));
    }
    res.pipe(file);
    file.on('finish', () => file.close(() => done(null)));
  }).on('error', (err) => {
    file.close();
    try { fs.unlinkSync(dest); } catch (_) {}
    done(err);
  });
}

// Burn subtitle from uploaded file
router.post('/api/burn-subtitle', upload.fields([
  { name: 'video', maxCount: 1 },
  { name: 'subtitle', maxCount: 1 },
]), (req, res) => {
  const { start, end, delogo, language } = req.body;
  const videoFile = req.files?.video?.[0];
  const subtitleFile = req.files?.subtitle?.[0];

  if (!videoFile || !subtitleFile || !start || !end) {
    return res.status(400).json({ error: '缺少参数：需要视频文件、字幕文件、开始时间、结束时间' });
  }

  const outputName = `output_${Date.now()}.mp4`;
  const outputPath = path.join(OUTPUT_DIR, outputName);
  const subPath = escapeSubPath(subtitleFile.path);

  probeResolution(videoFile.path, (width, height) => {
    resolveDelogoFilter(delogo, videoFile.path, width, height, (delogoFilter) => {
      const subFilter = `subtitles='${subPath}':force_style='FontName=Noto Sans,FontSize=24'`;
      const logoScale = Math.round(width * 0.06);
      const bounce = buildBounceOverlay();
      const baseFilter = delogoFilter ? `[0:v]${delogoFilter}[dl];${buildLogoFilter(logoScale)};[dl][logo]${bounce}` : `${buildLogoFilter(logoScale)};[0:v][logo]${bounce}`;
      const fc = `${baseFilter},${subFilter}[v]`;

      const args = [
        '-y',
        '-i', videoFile.path,
        '-i', LOGO_PATH,
        '-ss', start,
        '-to', end,
        '-filter_complex', fc,
        '-map', '[v]', '-map', '0:a',
        '-pix_fmt', 'yuv420p',
        outputPath,
      ];

      console.log('[Subtitle] Processing:', { start, end, delogo: !!delogoFilter, video: videoFile.originalname, subtitle: subtitleFile.originalname });

      execFile('ffmpeg', args, { timeout: 600000, maxBuffer: 10 * 1024 * 1024 }, (err, stdout, stderr) => {
        try { fs.unlinkSync(videoFile.path); } catch (_) {}
        try { fs.unlinkSync(subtitleFile.path); } catch (_) {}

        if (err) {
          console.error('[Subtitle] FFmpeg error:', stderr || err.message);
          return res.status(500).json({ error: 'FFmpeg 处理失败: ' + (stderr?.split('\n').pop() || err.message) });
        }

        saveMeta(outputName, { start, end, video: videoFile.originalname, subtitle: subtitleFile.originalname, language: language || '' });
        res.json({ ok: true, url: `/subtitle/output/${outputName}`, filename: outputName });
      });
    });
  });
});

// Burn subtitle from URL
router.post('/api/burn-subtitle-url', upload.fields([
  { name: 'subtitle', maxCount: 1 },
]), (req, res) => {
  const { videoUrl, subtitleUrl, start, end, delogo, language } = req.body;
  const subtitleFile = req.files?.subtitle?.[0];

  if (!videoUrl || !start || !end) {
    return res.status(400).json({ error: '缺少参数：需要视频链接、开始时间、结束时间' });
  }
  if (!subtitleFile && !subtitleUrl) {
    return res.status(400).json({ error: '缺少参数：需要字幕文件或字幕链接' });
  }

  const outputName = `output_${Date.now()}.mp4`;
  const outputPath = path.join(OUTPUT_DIR, outputName);

  function processWithVideo(videoInput, subFilePath, cleanupVideo) {
    const subPath = escapeSubPath(subFilePath);

    const isUrl = videoInput.startsWith('http://') || videoInput.startsWith('https://');

    const cleanup = () => {
      try { fs.unlinkSync(subFilePath); } catch (_) {}
      if (cleanupVideo) { try { fs.unlinkSync(videoInput); } catch (_) {} }
    };

    const finish = (err, stderr) => {
      cleanup();
      if (err) {
        console.error('[Subtitle-URL] FFmpeg error:', stderr || err.message);
        jobs.set(jobId, { status: 'error', error: 'FFmpeg 处理失败: ' + (stderr?.split('\n').pop() || err.message), created: Date.now() });
        return;
      }
      saveMeta(outputName, { start, end, videoUrl, subtitleUrl: subtitleUrl || '', language: language || '' });
      jobs.set(jobId, { status: 'done', url: `/subtitle/output/${outputName}`, filename: outputName, created: Date.now() });
      console.log('[Subtitle-URL] Job done:', jobId);
    };

    const run = () => {
      probeResolution(videoInput, (width, height) => {
        resolveDelogoFilter(delogo, videoInput, width, height, (delogoFilter) => {
          const subFilter = `subtitles='${subPath}':force_style='FontName=Noto Sans,FontSize=24'`;
          const logoScale = Math.round(width * 0.06);
          const bounce = buildBounceOverlay();
          const baseFilter = delogoFilter ? `[0:v]${delogoFilter}[dl];${buildLogoFilter(logoScale)};[dl][logo]${bounce}` : `${buildLogoFilter(logoScale)};[0:v][logo]${bounce}`;
          const fc = `${baseFilter},${subFilter}[v]`;

          // URLs: input-seeking (-ss before -i) sends HTTP Range → only downloads the clip segment
          // Local files: output-seeking (-ss after -i)
          const args = isUrl ? [
            '-y',
            '-ss', start,
            '-analyzeduration', '20000000',
            '-probesize', '20000000',
            '-i', videoInput,
            '-i', LOGO_PATH,
            '-t', calcDuration(start, end),
            '-filter_complex', fc,
            '-map', '[v]', '-map', '0:a',
            '-pix_fmt', 'yuv420p',
            outputPath,
          ] : [
            '-y',
            '-i', videoInput,
            '-i', LOGO_PATH,
            '-ss', start,
            '-to', end,
            '-filter_complex', fc,
            '-map', '[v]', '-map', '0:a',
            '-pix_fmt', 'yuv420p',
            outputPath,
          ];

          console.log('[Subtitle-URL] Processing:', { start, end, seek: isUrl ? 'input' : 'output', delogo: !!delogoFilter });
          execFile('ffmpeg', args, { timeout: 600000, maxBuffer: 10 * 1024 * 1024 }, (err, _out, stderr) => {
            finish(err, stderr);
          });
        });
      });
    };

    if (isUrl) {
      // Pre-check the URL before handing to FFmpeg — fail fast on server errors or timeout
      checkUrlStatus(videoInput).then((status) => {
        if (status === 0) {
          console.error('[Subtitle-URL] URL pre-check timed out / unreachable:', videoInput);
          cleanup();
          jobs.set(jobId, { status: 'error', error: '视频源服务器无响应，请稍后重试', created: Date.now() });
          return;
        }
        if (status >= 400) {
          console.error('[Subtitle-URL] URL pre-check failed, status:', status, videoInput);
          cleanup();
          jobs.set(jobId, { status: 'error', error: `视频源服务器暂时不可用 (HTTP ${status})，请稍后重试`, created: Date.now() });
          return;
        }
        run();
      });
    } else {
      run();
    }
  }

  // Return job ID immediately — process in background
  const jobId = `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  jobs.set(jobId, { status: 'pending', created: Date.now() });
  res.json({ ok: true, jobId });

  function processWithSubtitle(subFilePath) {
    // Pass URL directly — ffmpeg uses input seeking to only download the requested segment
    jobs.set(jobId, { status: 'processing', created: Date.now() });
    console.log('[Subtitle-URL] Processing via input seeking (no full download):', videoUrl);
    processWithVideo(videoUrl, subFilePath, false);
  }

  if (subtitleFile) {
    processWithSubtitle(subtitleFile.path);
  } else {
    const ext = path.extname(new URL(subtitleUrl).pathname) || '.srt';
    const subDest = path.join(UPLOAD_DIR, `${Date.now()}_${Math.random().toString(36).slice(2, 8)}${ext}`);
    console.log('[Subtitle-URL] Downloading subtitle from:', subtitleUrl);
    downloadFile(subtitleUrl, subDest, (err) => {
      if (err) {
        console.error('[Subtitle-URL] Subtitle download error:', err.message);
        jobs.set(jobId, { status: 'error', error: '字幕下载失败: ' + err.message, created: Date.now() });
        return;
      }
      processWithSubtitle(subDest);
    });
  }
});

// Job status endpoint
router.get('/api/job/:jobId', (req, res) => {
  const job = jobs.get(req.params.jobId);
  if (!job) return res.status(404).json({ status: 'error', error: 'Job not found (server restarted, please try again)' });
  res.json(job);
});

// List generated files (history)
router.get('/api/history', (req, res) => {
  try {
    const db = loadDB();
    const files = fs.readdirSync(OUTPUT_DIR)
      .filter(f => f.endsWith('.mp4'))
      .map(f => {
        try {
          const stat = fs.statSync(path.join(OUTPUT_DIR, f));
          const meta = db[f] || {};
          return { filename: f, size: stat.size, created: meta.created || stat.mtimeMs, ...meta };
        } catch (_) { return null; }
      })
      .filter(f => f && f.size > 10240)
      .sort((a, b) => b.created - a.created)
      .slice(0, 50);
    res.json({ ok: true, files });
  } catch (_) {
    res.json({ ok: true, files: [] });
  }
});

// Delete a generated file
router.delete('/api/history/:filename', (req, res) => {
  const filename = req.params.filename;
  if (!/^output_\d+\.mp4$/.test(filename)) return res.status(400).json({ error: '无效文件名' });
  const filePath = path.join(OUTPUT_DIR, filename);
  try { fs.unlinkSync(filePath); } catch (_) {}
  try { const db = loadDB(); delete db[filename]; saveDB(db); } catch (_) {}
  res.json({ ok: true });
});

// Download output file
router.get('/api/burn-subtitle/download/:filename', (req, res) => {
  const filePath = path.join(OUTPUT_DIR, req.params.filename);
  if (!fs.existsSync(filePath)) return res.status(404).send('文件不存在');
  res.download(filePath);
});

// Serve output files statically
router.use('/output', express.static(OUTPUT_DIR));

module.exports = router;
