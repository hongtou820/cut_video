const { AssemblyAI } = require('assemblyai');
const fs = require('fs');
const path = require('path');

const client = new AssemblyAI({ apiKey: '7b372c6797d442c4ba4316c504b69bf3' });

const VIDEO_PATH = '/Users/hongtou/Desktop/output.mp4';
const VTT_PATH = '/Users/hongtou/Desktop/output.vtt';

async function main() {
  console.log('Uploading video to AssemblyAI...');

  const transcript = await client.transcripts.transcribe({
    audio: VIDEO_PATH,
    language_detection: true,
    speech_models: ['universal-3-pro', 'universal-2'],
  });

  if (transcript.status === 'error') {
    console.error('Transcription failed:', transcript.error);
    process.exit(1);
  }

  console.log(`Transcription complete. Language: ${transcript.language_code}`);
  console.log(`Words: ${transcript.words?.length || 0}`);

  // Get VTT subtitles
  const vtt = await client.transcripts.subtitles(transcript.id, 'vtt');

  fs.writeFileSync(VTT_PATH, vtt);
  console.log(`Saved VTT to: ${VTT_PATH}`);

  // Also save SRT as backup
  const srt = await client.transcripts.subtitles(transcript.id, 'srt');
  fs.writeFileSync('/Users/hongtou/Desktop/output.srt', srt);
  console.log('Also saved SRT to: /Users/hongtou/Desktop/output.srt');

  // Print preview
  console.log('\n--- VTT Preview ---');
  console.log(vtt.substring(0, 500));
}

main().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
