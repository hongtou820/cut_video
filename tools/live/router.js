const express  = require('express');
const { spawn } = require('child_process');
const path      = require('path');
const fs        = require('fs');

const router   = express.Router();
const LIVE_DIR = path.join(__dirname, 'output');

if (!fs.existsSync(LIVE_DIR)) fs.mkdirSync(LIVE_DIR, { recursive: true });

// id -> { process, startedAt, srcUrl, pid }
const relays = new Map();

function makeId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
}

/*
 * POST /live/api/start
 * body: {
 *   src        : "https://...m3u8"   (required)
 *   delogo     : { x, y, w, h }      (optional — covers watermark with blur)
 *   cover      : { x, y, w, h }      (optional — covers with black box, faster than delogo)
 *   logo_text  : "your-site.com"     (optional — draws your own text top-left)
 * }
 */
router.post('/api/start', (req, res) => {
  const { src, delogo, cover, logo_text } = req.body || {};
  if (!src) return res.status(400).json({ error: 'src required' });

  const id     = makeId();
  const outDir = path.join(LIVE_DIR, id);
  fs.mkdirSync(outDir, { recursive: true });

  const outM3u8 = path.join(outDir, 'index.m3u8');
  const segPat  = path.join(outDir, 'seg%05d.ts');

  // Build -vf filter chain
  const vfParts = [];

  if (delogo) {
    const { x = 0, y = 0, w = 300, h = 80 } = delogo;
    vfParts.push(`delogo=x=${x}:y=${y}:w=${w}:h=${h}`);
  }

  if (cover) {
    const { x = 0, y = 0, w = 300, h = 80 } = cover;
    // fill with black box — much faster than delogo
    vfParts.push(`drawbox=x=${x}:y=${y}:w=${w}:h=${h}:color=black:t=fill`);
  }

  if (logo_text) {
    const safe = logo_text.replace(/'/g, '');
    vfParts.push(
      `drawtext=text='${safe}':fontcolor=white:fontsize=22:x=10:y=8:shadowx=1:shadowy=1:shadowcolor=black`
    );
  }

  const ffmpegArgs = [
    '-protocol_whitelist', 'file,http,https,tcp,tls,crypto',
    '-allowed_extensions', 'ALL',
    '-i', src,
    ...(vfParts.length ? ['-vf', vfParts.join(',')] : ['-c:v', 'copy']),
    ...(vfParts.length ? ['-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency'] : []),
    '-c:a', 'aac', '-b:a', '128k',
    '-f', 'hls',
    '-hls_time', '2',
    '-hls_list_size', '10',
    '-hls_flags', 'delete_segments+append_list',
    '-hls_segment_filename', segPat,
    outM3u8,
  ];

  console.log('[live] starting relay', id, 'src:', src);

  const proc = spawn('ffmpeg', ffmpegArgs, { windowsHide: true });

  proc.stderr.on('data', d => process.stdout.write('[live/' + id + '] ' + d));
  proc.on('exit', (code, sig) => {
    console.log(`[live/${id}] exited code=${code} sig=${sig}`);
    relays.delete(id);
  });

  relays.set(id, { process: proc, startedAt: Date.now(), srcUrl: src, pid: proc.pid });

  res.json({ ok: true, id, url: `/live/output/${id}/index.m3u8` });
});

// GET /live/api/list  — active relays
router.get('/api/list', (_req, res) => {
  const list = [];
  for (const [id, r] of relays) {
    list.push({ id, startedAt: r.startedAt, srcUrl: r.srcUrl, pid: r.pid });
  }
  res.json(list);
});

// DELETE /live/api/stop/:id
router.delete('/api/stop/:id', (req, res) => {
  const relay = relays.get(req.params.id);
  if (!relay) return res.status(404).json({ error: 'not found' });
  relay.process.kill('SIGTERM');
  relays.delete(req.params.id);
  res.json({ ok: true, stopped: req.params.id });
});

// Serve HLS output files
router.use('/output', express.static(LIVE_DIR));

module.exports = router;
