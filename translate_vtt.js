const https = require('https');
const fs = require('fs');

// Use Google Translate (free, no key needed)
const VTT_PATH = '/Users/hongtou/Desktop/output.vtt';
const OUTPUT_PATH = '/Users/hongtou/Desktop/output_zh.vtt';

function translate(text, from, to) {
  return new Promise((resolve, reject) => {
    const url = `https://translate.googleapis.com/translate_a/single?client=gtx&sl=${from}&tl=${to}&dt=t&q=${encodeURIComponent(text)}`;
    https.get(url, { headers: { 'User-Agent': 'Mozilla/5.0' } }, res => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          const translated = parsed[0].map(s => s[0]).join('');
          resolve(translated);
        } catch (e) {
          reject(new Error(`Parse error: ${data.substring(0, 200)}`));
        }
      });
    }).on('error', reject);
  });
}

async function main() {
  const vtt = fs.readFileSync(VTT_PATH, 'utf-8');

  // Parse VTT into blocks
  const lines = vtt.split('\n');
  const blocks = [];
  let current = null;

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.match(/^\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}\.\d{3}/)) {
      current = { time: trimmed, text: '' };
      blocks.push(current);
    } else if (current && trimmed) {
      current.text += (current.text ? ' ' : '') + trimmed;
    } else if (trimmed === '' && current) {
      current = null;
    }
  }

  console.log(`Found ${blocks.length} subtitle blocks. Translating ja -> zh-CN...`);

  // Translate in batches of 5
  const translated = [];
  for (let i = 0; i < blocks.length; i += 5) {
    const batch = blocks.slice(i, i + 5);
    const promises = batch.map(async (b, idx) => {
      // Remove spaces between Japanese characters for better translation
      const cleanText = b.text.replace(/\s+/g, '');
      try {
        const zh = await translate(cleanText, 'ja', 'zh-CN');
        translated[i + idx] = zh;
        console.log(`[${i + idx}] ${cleanText} -> ${zh}`);
      } catch (e) {
        console.log(`[${i + idx}] FAIL: ${e.message}`);
        translated[i + idx] = b.text;
      }
    });
    await Promise.all(promises);
    // Small delay to avoid rate limiting
    await new Promise(r => setTimeout(r, 200));
  }

  // Build translated VTT
  let output = 'WEBVTT\n\n';
  for (let i = 0; i < blocks.length; i++) {
    output += `${blocks[i].time}\n${translated[i] || blocks[i].text}\n\n`;
  }

  fs.writeFileSync(OUTPUT_PATH, output);
  console.log(`\nSaved Chinese VTT to: ${OUTPUT_PATH}`);
}

main().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
