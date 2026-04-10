# Subtitle Tool — Technical Reference

## Project Structure / Key Files

```
cut_video/
├── server.js                          # Main Express app (port 3000)
│   ├── app.use('/subtitle', subtitleRouter)
│   └── app.use('/clipper',  clipperRouter)
│
└── tools/
    └── subtitle/
        ├── router.js                  # All API logic — ffmpeg, delogo, logo overlay
        ├── index.html                 # Frontend UI
        ├── AIJAV LOGO_SQUARE_BLACK.png  # Watermark logo added to every output
        ├── db.json                    # Auto-generated metadata store (history)
        ├── uploads/                   # Temp dir for uploaded video/subtitle files
        └── output/                    # Final rendered .mp4 files served statically
```

### Key functions in `router.js`

| Function | Purpose |
|---|---|
| `probeResolution(inputPath, cb)` | Runs `ffprobe` to get video `width × height` — used to calculate delogo regions and logo size |
| `buildDelogoFilter(delogoStr, w, h)` | Parses the `delogo` JSON param and returns a delogo filter string (or empty string if none) |
| `clampDelogo(x, y, w, h, width, height)` | Clamps delogo coords to stay 2px inside frame edges (avoids ffmpeg "outside of frame" error) |
| `buildLogoFilter(logoScale)` | Returns the `[1:v]scale,geq,format` filter string for the AIJAV logo with rounded corners |
| `downloadFile(url, dest, cb)` | Downloads subtitle (or could be video) via HTTP/HTTPS with redirect support |

---

## The ffmpeg Command (burn-subtitle-url)

**Route:** `POST /subtitle/api/burn-subtitle-url`

The command assembled at [router.js:230-239](../tools/subtitle/router.js#L230):

```bash
ffmpeg -y \
  -i <videoUrl>          \   # input 0: video stream (direct URL, ffmpeg fetches it)
  -i <LOGO_PATH>         \   # input 1: AIJAV logo PNG
  -ss <start>            \   # seek to start time (HH:MM:SS)
  -to <end>              \   # end time (HH:MM:SS)
  -filter_complex <fc>   \   # full filter graph (see below)
  -map '[v]'             \   # output mapped from filter graph
  -map 0:a               \   # audio passthrough from input 0
  <outputPath>
```

**Note:** `-ss` / `-to` are placed *after* `-i`, so ffmpeg decodes from the beginning up to `start`. For long videos this is slow. Placing `-ss` *before* `-i` would be faster (keyframe seek) but less precise with subtitles.

**Process timeout:** 600,000 ms (10 minutes) — set in `execFile` options at [router.js:243](../tools/subtitle/router.js#L243).

---

## How delogo Is Applied in the Filter Chain

The `delogo` body param is a JSON string with either a **preset** or **custom coordinates**:

```json
// Preset examples
{ "preset": "both-top" }       // removes both top-left and top-right watermarks
{ "preset": "top-left" }
{ "preset": "top-right" }
{ "preset": "bottom-left" }
{ "preset": "bottom-right" }

// Custom coordinates (pixels)
{ "x": 0, "y": 0, "w": 200, "h": 36 }
```

### Preset region sizes (relative to video resolution)

| Region | Width | Height |
|---|---|---|
| Left watermark (e.g. JAVRATE.COM) | 14% of video width | 12% of video height |
| Right watermark (e.g. IPPA logo) | 12% of video width | 14% of video height |

`clampDelogo` enforces a 2px band margin on all sides to prevent the ffmpeg delogo filter error: `"logo area is outside of the frame"`.

---

## filter_complex Usage

The full filter graph is built in `fc` and passed to `-filter_complex`. There are two variants:

### Case 1 — With delogo

```
[0:v]<delogoFilter>[dl];
<logoFilter>;
[dl][logo]overlay=W-w-10:10,
subtitles='<subPath>':force_style='FontName=Noto Sans,FontSize=24'[v]
```

### Case 2 — Without delogo

```
<logoFilter>;
[0:v][logo]overlay=W-w-10:10,
subtitles='<subPath>':force_style='FontName=Noto Sans,FontSize=24'[v]
```

Where `<logoFilter>` expands to:

```
[1:v]scale=<logoScale>:-1,format=rgba,geq=r=r(X,Y):g=g(X,Y):b=b(X,Y):a=if(gt(abs(X-W/2),W/2-CR)*gt(abs(Y-H/2),H/2-CR),if(lte(hypot(...),CR),alpha(X,Y),0),alpha(X,Y))[logo]
```

- `logoScale` = `round(videoWidth × 0.06)` — logo is 6% of video width
- `CR` (corner radius) = `round(logoScale × 0.15)`
- Logo is overlaid at `W-w-10:10` = top-right corner, 10px from edge

### Full execution order in the filter graph

```
Input 0 (video)
    │
    ├─[if delogo]──► delogo (top-left region) ──► delogo (top-right region) ──► [dl]
    │
Input 1 (logo PNG)
    └──► scale → format=rgba → geq (rounded corners) ──► [logo]
    │
[dl or 0:v] + [logo] ──► overlay=W-w-10:10 ──► subtitles burn-in ──► [v]
```

---

## Adding a Second Watermark Overlay

To add an additional image watermark (e.g. a second logo or text bug), insert another overlay **after** the existing AIJAV logo overlay and **before** the subtitles filter.

### Example — add a second PNG at bottom-left

Add a third input (`-i <secondLogo>`) and extend the filter graph:

```js
// In buildLogoFilter or a new buildSecondLogoFilter:
`[2:v]scale=${logoScale2}:-1,format=rgba[logo2]`

// Chain in filter_complex:
`[dl][logo]overlay=W-w-10:10[with_logo1];[with_logo1][logo2]overlay=10:H-h-10,subtitles=...[v]`
```

Key points:
- Each overlay consumes two labeled streams and produces one output label
- The subtitles filter must always be **last** in the chain (it does not support labeled output, it chains directly)
- All commas inside `geq=` expressions must be escaped as `\\,` when inside a `-filter_complex` string

---

## Timeout Summary

| Layer | Current limit | Risk |
|---|---|---|
| `ffprobe` resolution probe | 30s | Low |
| `ffmpeg` burn process | **10 min** | Medium — long clips or slow URLs will fail |
| Express HTTP connection | None set | Proxy/CDN may cut at 60–120s |

To handle long jobs safely, the recommended fix is an async job queue: return a job ID immediately, run ffmpeg in background, poll `GET /api/status/:jobId`.
