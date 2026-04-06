const express = require('express');
const fs = require('fs');
const path = require('path');
const { execFile, spawn } = require('child_process');
const multer = require('multer');

const router = express.Router();

const upload = multer({
  dest: path.join(__dirname, 'uploads'),
  limits: { fileSize: 500 * 1024 * 1024 }, // 500MB
});

const UPLOAD_DIR = path.join(__dirname, 'uploads');
const OUTPUT_DIR = path.join(__dirname, 'output');
const DB_PATH = path.join(__dirname, 'db.json');
if (!fs.existsSync(UPLOAD_DIR)) fs.mkdirSync(UPLOAD_DIR, { recursive: true });
if (!fs.existsSync(OUTPUT_DIR)) fs.mkdirSync(OUTPUT_DIR, { recursive: true });

// Simple JSON DB
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

// Extract clean Douyin URL from pasted text (may contain extra text)
function extractDouyinUrl(text) {
  const match = text.match(/https?:\/\/[^\s]+douyin[^\s]*/i);
  return match ? match[0] : text.trim();
}

// Resolve video info using Playwright-based resolver
const RESOLVER_PATH = path.join(__dirname, 'douyin-resolver.py');

router.post('/api/resolve', express.json(), (req, res) => {
  const rawUrl = req.body.url;
  if (!rawUrl) return res.status(400).json({ error: '请输入链接' });

  const url = extractDouyinUrl(rawUrl);
  console.log('[Clipper] Resolving:', url);

  execFile('python3', [RESOLVER_PATH, url], {
    timeout: 120000,
    maxBuffer: 10 * 1024 * 1024,
  }, (err, stdout, stderr) => {
    if (err) {
      console.error('[Clipper] Resolver error:', stderr || err.message);
      // Try parse stdout anyway (might have error JSON)
      try {
        const errData = JSON.parse(stdout);
        return res.status(500).json({ error: '解析失败: ' + (errData.error || err.message) });
      } catch (_) {}
      return res.status(500).json({ error: '解析失败: ' + (stderr?.split('\n').filter(l => l).pop() || err.message) });
    }
    try {
      const info = JSON.parse(stdout);
      if (!info.ok) return res.status(500).json({ error: info.error || '解析失败' });
      res.json({
        ok: true,
        title: info.title || '',
        duration: info.duration || 0,
        thumbnail: info.thumbnail || '',
        videoUrl: info.videoUrl || '',
      });
    } catch (e) {
      res.status(500).json({ error: '解析返回数据异常' });
    }
  });
});

// Clip video from URL - resolve then download then clip
router.post('/api/clip', express.json(), (req, res) => {
  const { url, start, end, title } = req.body;
  if (!url) return res.status(400).json({ error: '请先解析视频链接' });
  if (!start || !end) return res.status(400).json({ error: '请输入开始和结束时间' });

  const cleanUrl = extractDouyinUrl(url);
  const outputName = `clip_${Date.now()}.mp4`;
  const outputPath = path.join(OUTPUT_DIR, outputName);
  const tempPath = path.join(UPLOAD_DIR, `temp_${Date.now()}.mp4`);

  console.log('[Clipper] Resolving & clipping:', { url: cleanUrl, start, end });

  // Step 1: Resolve video URL using Playwright
  execFile('python3', [RESOLVER_PATH, cleanUrl], {
    timeout: 120000,
    maxBuffer: 10 * 1024 * 1024,
  }, (err, stdout, stderr) => {
    if (err) {
      console.error('[Clipper] Resolve error:', stderr || err.message);
      return res.status(500).json({ error: '视频解析失败' });
    }

    let videoUrl;
    try {
      const info = JSON.parse(stdout);
      videoUrl = info.videoUrl;
      if (!videoUrl) return res.status(500).json({ error: '无法获取视频地址' });
    } catch (e) {
      return res.status(500).json({ error: '解析返回数据异常' });
    }

    // Step 2: Download video with ffmpeg directly from URL (supports http)
    console.log('[Clipper] Downloading video...');
    const dlArgs = ['-y', '-i', videoUrl, '-c', 'copy', tempPath];
    execFile('ffmpeg', dlArgs, { timeout: 300000, maxBuffer: 10 * 1024 * 1024 }, (dlErr) => {
      if (dlErr) {
        // Fallback: try wget
        execFile('wget', ['-q', '-O', tempPath, videoUrl], { timeout: 300000 }, (wgetErr) => {
          if (wgetErr) {
            return res.status(500).json({ error: '视频下载失败' });
          }
          doClip();
        });
        return;
      }
      doClip();
    });

    function doClip() {
      const args = [
        '-y', '-i', tempPath,
        '-ss', start, '-to', end,
        '-c:v', 'libx264', '-c:a', 'aac',
        '-movflags', '+faststart',
        outputPath,
      ];

      console.log('[Clipper] FFmpeg clipping:', { start, end });

      execFile('ffmpeg', args, { timeout: 300000, maxBuffer: 10 * 1024 * 1024 }, (err, stdout, stderr) => {
        try { fs.unlinkSync(tempPath); } catch (_) {}

        if (err) {
          console.error('[Clipper] FFmpeg error:', stderr || err.message);
          return res.status(500).json({ error: 'FFmpeg 切片失败' });
        }

        saveMeta(outputName, { start, end, title: title || '', sourceUrl: cleanUrl });
        res.json({ ok: true, url: `/clipper/output/${outputName}`, filename: outputName });
      });
    }
  });
});

// Clip uploaded file
router.post('/api/clip-upload', upload.single('video'), (req, res) => {
  if (!req.file) return res.status(400).json({ error: '请上传视频文件' });
  const { start, end } = req.body;
  if (!start || !end) return res.status(400).json({ error: '请输入开始和结束时间' });

  const tempPath = req.file.path;
  const outputName = `clip_${Date.now()}.mp4`;
  const outputPath = path.join(OUTPUT_DIR, outputName);

  console.log('[Clipper] Clipping uploaded file:', { file: req.file.originalname, start, end });

  const args = [
    '-y',
    '-i', tempPath,
    '-ss', start,
    '-to', end,
    '-c:v', 'libx264',
    '-c:a', 'aac',
    '-movflags', '+faststart',
    outputPath,
  ];

  execFile('ffmpeg', args, { timeout: 300000, maxBuffer: 10 * 1024 * 1024 }, (err, stdout, stderr) => {
    // Clean up uploaded temp file
    try { fs.unlinkSync(tempPath); } catch (_) {}

    if (err) {
      console.error('[Clipper] FFmpeg error:', stderr || err.message);
      return res.status(500).json({ error: 'FFmpeg 切片失败' });
    }

    saveMeta(outputName, { start, end, title: req.file.originalname || '' });
    res.json({ ok: true, url: `/clipper/output/${outputName}`, filename: outputName });
  });
});

// History
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
      .filter(f => f && f.size > 1024)
      .sort((a, b) => b.created - a.created)
      .slice(0, 50);
    res.json({ ok: true, files });
  } catch (_) {
    res.json({ ok: true, files: [] });
  }
});

// Delete history
router.delete('/api/history/:filename', (req, res) => {
  const filename = req.params.filename;
  if (!/^clip_\d+\.mp4$/.test(filename)) return res.status(400).json({ error: '无效文件名' });
  const filePath = path.join(OUTPUT_DIR, filename);
  try { fs.unlinkSync(filePath); } catch (_) {}
  try { const db = loadDB(); delete db[filename]; saveDB(db); } catch (_) {}
  res.json({ ok: true });
});

// Download
router.get('/api/download/:filename', (req, res) => {
  const filePath = path.join(OUTPUT_DIR, req.params.filename);
  if (!fs.existsSync(filePath)) return res.status(404).send('文件不存在');
  res.download(filePath);
});

// Serve output files
router.use('/output', express.static(OUTPUT_DIR));

module.exports = router;
