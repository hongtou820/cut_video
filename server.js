const express = require('express');
const Anthropic = require('@anthropic-ai/sdk');
const fs = require('fs');
const path = require('path');
const https = require('https');

process.on('uncaughtException', (err) => {
  console.error('[Server] Uncaught exception (server kept alive):', err.message);
});

// Database module (graceful - app works without it)
let db;
try {
  db = require('./db');
  db.initDB();
  console.log('[Server] SQLite database loaded successfully');
} catch (err) {
  console.warn('[Server] SQLite database unavailable, using in-memory only:', err.message);
  db = null;
}

// Generic HTTPS POST helper for OpenAI-compatible APIs
function apiPost(url, headers, body) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(url);
    const data = JSON.stringify(body);
    const req = https.request({
      hostname: parsed.hostname,
      path: parsed.pathname,
      method: 'POST',
      headers: { ...headers, 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data) },
    }, (res) => {
      let chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => {
        try { resolve(JSON.parse(Buffer.concat(chunks).toString())); }
        catch (e) { reject(new Error('Invalid JSON response')); }
      });
    });
    req.on('error', reject);
    req.write(data);
    req.end();
  });
}

const app = express();
const PORT = process.env.PORT || 3003;

app.use(express.static('public'));
app.use(express.json());

// Character image proxy - fetches from wiki and caches locally
const IMG_CACHE_DIR = path.join(__dirname, 'public/img/cache');
if (!fs.existsSync(IMG_CACHE_DIR)) fs.mkdirSync(IMG_CACHE_DIR, { recursive: true });

const CHAR_IMAGES = {
  luffy: 'https://static.wikia.nocookie.net/onepiece/images/6/6d/Monkey_D._Luffy_Anime_Post_Timeskip_Infobox.png/revision/latest?cb=20240306200817',
  zoro: 'https://static.wikia.nocookie.net/onepiece/images/5/52/Roronoa_Zoro_Anime_Post_Timeskip_Infobox.png/revision/latest?cb=20141008195159',
  sanji: 'https://static.wikia.nocookie.net/onepiece/images/b/b6/Sanji_Anime_Post_Timeskip_Infobox.png/revision/latest?cb=20170625125657',
  ace: 'https://static.wikia.nocookie.net/onepiece/images/4/4f/Portgas_D._Ace_Anime_Infobox.png/revision/latest?cb=20240629132600',
  law: 'https://static.wikia.nocookie.net/onepiece/images/4/4d/Trafalgar_D._Water_Law_Anime_Post_Timeskip_Infobox.png/revision/latest?cb=20230124163510',
  shanks: 'https://static.wikia.nocookie.net/onepiece/images/6/66/Shanks_Anime_Infobox.png/revision/latest?cb=20180607083158',
  chopper: 'https://static.wikia.nocookie.net/onepiece/images/a/af/Tony_Tony_Chopper_Anime_Post_Timeskip_Infobox.png/revision/latest?cb=20240720150824',
  nami: 'https://static.wikia.nocookie.net/onepiece/images/6/68/Nami_Anime_Post_Timeskip_Infobox.png/revision/latest?cb=20190720162446',
  robin: 'https://static.wikia.nocookie.net/onepiece/images/b/bc/Nico_Robin_Anime_Post_Timeskip_Infobox.png/revision/latest?cb=20190202051257',
  hancock: 'https://static.wikia.nocookie.net/onepiece/images/f/f0/Boa_Hancock_Anime_Infobox.png/revision/latest?cb=20230126022456',
  vivi: 'https://static.wikia.nocookie.net/onepiece/images/0/09/Nefertari_Vivi_Anime_Post_Timeskip_Infobox.png/revision/latest?cb=20190505023647',
  perona: 'https://static.wikia.nocookie.net/onepiece/images/a/ad/Perona_Anime_Pre_Timeskip_Infobox.png/revision/latest?cb=20160812223500',
  yamato: 'https://static.wikia.nocookie.net/onepiece/images/b/bd/Yamato_Anime_Infobox.png/revision/latest?cb=20220119060149',
  reiju: 'https://static.wikia.nocookie.net/onepiece/images/a/a3/Vinsmoke_Reiju_Anime_Infobox.png/revision/latest?cb=20170423121650',
  sabo: 'https://static.wikia.nocookie.net/onepiece/images/c/c2/Sabo_Anime_Infobox.png/revision/latest?cb=20230804035141',
  katakuri: 'https://static.wikia.nocookie.net/onepiece/images/2/2e/Charlotte_Katakuri_Anime_Infobox.png/revision/latest?cb=20230204155539',
  doflamingo: 'https://static.wikia.nocookie.net/onepiece/images/7/7e/Donquixote_Doflamingo_Anime_Infobox.png/revision/latest?cb=20231017082245',
  mihawk: 'https://static.wikia.nocookie.net/onepiece/images/b/bf/Dracule_Mihawk_Anime_Infobox.png/revision/latest?cb=20151222105910',
  crocodile: 'https://static.wikia.nocookie.net/onepiece/images/f/fd/Crocodile_Anime_Infobox.png/revision/latest?cb=20230125235528',
  marco: 'https://static.wikia.nocookie.net/onepiece/images/2/2c/Marco_Anime_Post_Timeskip_Infobox.png/revision/latest?cb=20221010015200',
  kid: 'https://static.wikia.nocookie.net/onepiece/images/4/47/Eustass_Kid_Anime_Post_Timeskip_Infobox.png/revision/latest?cb=20240505021859',
  blackbeard: 'https://static.wikia.nocookie.net/onepiece/images/f/ff/Marshall_D._Teach_Anime_Post_Timeskip_Infobox.png/revision/latest?cb=20240128044952',
  shirahoshi: 'https://static.wikia.nocookie.net/onepiece/images/c/c1/Shirahoshi_Anime_Infobox.png/revision/latest?cb=20240814220909',
  pudding: 'https://static.wikia.nocookie.net/onepiece/images/6/60/Charlotte_Pudding_Anime_Infobox.png/revision/latest?cb=20250106015531',
  koala: 'https://static.wikia.nocookie.net/onepiece/images/3/3d/Koala_Anime_Infobox.png/revision/latest?cb=20140928211728',
  carrot: 'https://static.wikia.nocookie.net/onepiece/images/e/e2/Carrot_Anime_Infobox.png/revision/latest?cb=20180826142459',
  uta: 'https://static.wikia.nocookie.net/onepiece/images/0/06/Uta_Anime_Infobox.png/revision/latest?cb=20250818013702',
  bonney: 'https://static.wikia.nocookie.net/onepiece/images/6/62/Jewelry_Bonney_Anime_Post_Timeskip_Infobox.png/revision/latest?cb=20230123001318',
  tashigi: 'https://static.wikia.nocookie.net/onepiece/images/1/1e/Tashigi_Anime_Post_Timeskip_Infobox.png/revision/latest?cb=20251127120726',
  baby5: 'https://static.wikia.nocookie.net/onepiece/images/e/e1/Baby_5_Anime_Infobox.png/revision/latest?cb=20221011013323',
  franky: 'https://static.wikia.nocookie.net/onepiece/images/8/8c/Franky_Anime_Post_Timeskip_Infobox.png/revision/latest?cb=20241110020715',
  brook: 'https://static.wikia.nocookie.net/onepiece/images/4/41/Brook_Anime_Post_Timeskip_Infobox.png/revision/latest?cb=20161016160925',
  usopp: 'https://static.wikia.nocookie.net/onepiece/images/3/35/Usopp_Anime_Post_Timeskip_Infobox.png/revision/latest?cb=20221127233827',
  jinbe: 'https://static.wikia.nocookie.net/onepiece/images/8/81/Jinbe_Anime_Infobox.png/revision/latest?cb=20170521201349',
  rayleigh: 'https://static.wikia.nocookie.net/onepiece/images/b/b1/Silvers_Rayleigh_Anime_Infobox.png/revision/latest?cb=20230601221758',
  aokiji: 'https://static.wikia.nocookie.net/onepiece/images/d/d6/Kuzan_Anime_Post_Timeskip_Infobox.png/revision/latest?cb=20240811021341',
  akainu: 'https://static.wikia.nocookie.net/onepiece/images/d/d7/Sakazuki_Anime_Post_Timeskip_Infobox.png/revision/latest?cb=20220829052511',
  whitebeard: 'https://static.wikia.nocookie.net/onepiece/images/b/b7/Edward_Newgate_Anime_Infobox.png/revision/latest?cb=20220926165737',
  fujitora: 'https://static.wikia.nocookie.net/onepiece/images/e/e8/Issho_Anime_Infobox.png/revision/latest?cb=20220718140829',
  monet: 'https://static.wikia.nocookie.net/onepiece/images/9/98/Monet_Anime_Infobox.png/revision/latest?cb=20140616000310',
  viola: 'https://static.wikia.nocookie.net/onepiece/images/d/d7/Viola_Anime_Infobox.png/revision/latest?cb=20221027021751',
  hiyori: 'https://static.wikia.nocookie.net/onepiece/images/9/97/Kouzuki_Hiyori_Anime_Infobox.png/revision/latest?cb=20200811195812',
  rebecca: 'https://static.wikia.nocookie.net/onepiece/images/f/f6/Rebecca_Anime_Infobox.png/revision/latest?cb=20190519094508',
  smoothie: 'https://static.wikia.nocookie.net/onepiece/images/c/c5/Charlotte_Smoothie_Anime_Infobox.png/revision/latest?cb=20180423150946',
  stussy: 'https://static.wikia.nocookie.net/onepiece/images/e/ee/Stussy_Anime_Infobox.png/revision/latest?cb=20240512081047',
  ulti: 'https://static.wikia.nocookie.net/onepiece/images/d/dc/Ulti_Anime_Infobox.png/revision/latest?cb=20240831170217',
  blackmaria: 'https://static.wikia.nocookie.net/onepiece/images/e/e2/Black_Maria_Anime_Infobox.png/revision/latest?cb=20210808144206',
  sugar: 'https://static.wikia.nocookie.net/onepiece/images/e/e9/Sugar_Anime_Infobox.png/revision/latest?cb=20141005232110',
  kalifa: 'https://static.wikia.nocookie.net/onepiece/images/b/b3/Kalifa_Anime_Post_Timeskip_Infobox.png/revision/latest?cb=20240915021516',
  kizaru: 'https://static.wikia.nocookie.net/onepiece/images/1/14/Borsalino_Anime_Infobox.png/revision/latest?cb=20190603023753',
  alvida: 'https://static.wikia.nocookie.net/onepiece/images/c/cd/Alvida_Anime_Infobox.png/revision/latest?cb=20221116234952',
  nojiko: 'https://static.wikia.nocookie.net/onepiece/images/2/2d/Nojiko_Anime_Post_Timeskip_Infobox.png/revision/latest?cb=20251109161125',
  kaya: 'https://static.wikia.nocookie.net/onepiece/images/f/f5/Kaya_Manga_Post_Timeskip_Infobox.png/revision/latest?cb=20180617114926',
  makino: 'https://static.wikia.nocookie.net/onepiece/images/5/5a/Makino_Anime_Post_Timeskip_Infobox.png/revision/latest?cb=20240914133612',
  bellemere: 'https://static.wikia.nocookie.net/onepiece/images/3/3f/Bell-m%C3%A8re_Anime_Infobox.png/revision/latest?cb=20231128171918',
  olvia: 'https://static.wikia.nocookie.net/onepiece/images/f/fc/Nico_Olvia_Anime_Infobox.png/revision/latest?cb=20180131184905',
  hina: 'https://static.wikia.nocookie.net/onepiece/images/0/0d/Hina_Anime_Infobox.png/revision/latest?cb=20231125233601',
  gion: 'https://static.wikia.nocookie.net/onepiece/images/f/fb/Gion_Anime_Infobox.png/revision/latest?cb=20221101153309',
  tsuru: 'https://static.wikia.nocookie.net/onepiece/images/9/91/Tsuru_Anime_Infobox.png/revision/latest?cb=20240730231455',
  miss_valentine: 'https://static.wikia.nocookie.net/onepiece/images/b/bc/Mikita_Anime_Infobox.png/revision/latest?cb=20230417164634',
  paula: 'https://static.wikia.nocookie.net/onepiece/images/6/60/Zala_Anime_Infobox.png/revision/latest?cb=20221003164424',
  miss_goldenweek: 'https://static.wikia.nocookie.net/onepiece/images/b/b4/Marianne_Anime_Infobox.png/revision/latest?cb=20250115010211',
  conis: 'https://static.wikia.nocookie.net/onepiece/images/9/9f/Conis_Anime_Post_Timeskip_Infobox.png/revision/latest?cb=20251207162322',
  laki: 'https://static.wikia.nocookie.net/onepiece/images/c/c3/Raki_Anime_Infobox.png/revision/latest?cb=20161029212453',
  marguerite: 'https://static.wikia.nocookie.net/onepiece/images/c/cc/Marguerite_Anime_Infobox.png/revision/latest?cb=20140928162219',
  sandersonia: 'https://static.wikia.nocookie.net/onepiece/images/8/8c/Boa_Sandersonia_Anime_Infobox.png/revision/latest?cb=20141017161424',
  marigold: 'https://static.wikia.nocookie.net/onepiece/images/6/6c/Boa_Marigold_Anime_Infobox.png/revision/latest?cb=20150903140509',
  kikyo_kuja: 'https://static.wikia.nocookie.net/onepiece/images/d/d5/Kikyo_Anime_Infobox.png/revision/latest?cb=20131126094301',
  aphelandra: 'https://static.wikia.nocookie.net/onepiece/images/3/31/Aphelandra_Anime_Infobox.png/revision/latest?cb=20140928162409',
  sweet_pea: 'https://static.wikia.nocookie.net/onepiece/images/5/50/Sweet_Pea_Anime_Infobox.png/revision/latest?cb=20140928162454',
  shakky: 'https://static.wikia.nocookie.net/onepiece/images/e/e8/Shakuyaku_Anime_Infobox.png/revision/latest?cb=20241117020947',
  camie: 'https://static.wikia.nocookie.net/onepiece/images/a/af/Camie_Anime_Post_Timeskip_Infobox.png/revision/latest?cb=20130912213617',
  ishilly: 'https://static.wikia.nocookie.net/onepiece/images/c/c6/Ishilly_Anime_Infobox.png/revision/latest?cb=20130912210139',
  madame_shirley: 'https://static.wikia.nocookie.net/onepiece/images/6/61/Shyarly_Anime_Infobox.png/revision/latest?cb=20131112030157',
  otohime: 'https://static.wikia.nocookie.net/onepiece/images/c/c7/Otohime_Anime_Infobox.png/revision/latest?cb=20130427195608',
  sadi: 'https://static.wikia.nocookie.net/onepiece/images/3/38/Sadi_Anime_Infobox.png/revision/latest?cb=20221023232535',
  domino: 'https://static.wikia.nocookie.net/onepiece/images/1/11/Domino_Manga_Post_Timeskip_Infobox.png/revision/latest?cb=20170312041522',
  big_mom: 'https://static.wikia.nocookie.net/onepiece/images/d/d8/Charlotte_Linlin_Anime_Infobox.png/revision/latest?cb=20180423150804',
  lola: 'https://static.wikia.nocookie.net/onepiece/images/f/f0/Charlotte_Lola_Manga_Post_Timeskip_Infobox.png/revision/latest?cb=20201012081800',
  chiffon: 'https://static.wikia.nocookie.net/onepiece/images/6/6d/Charlotte_Chiffon_Anime_Infobox.png/revision/latest?cb=20170409062554',
  brulee: 'https://static.wikia.nocookie.net/onepiece/images/d/d9/Charlotte_Br%C3%BBl%C3%A9e_Anime_Infobox.png/revision/latest?cb=20170611174235',
  flampe: 'https://static.wikia.nocookie.net/onepiece/images/9/91/Charlotte_Flampe_Anime_Infobox.png/revision/latest?cb=20190203105539',
  amande: 'https://static.wikia.nocookie.net/onepiece/images/b/b9/Charlotte_Amande_Anime_Infobox.png/revision/latest?cb=20171016155845',
  galette: 'https://static.wikia.nocookie.net/onepiece/images/7/71/Charlotte_Galette_Anime_Infobox.png/revision/latest?cb=20180721222625',
  compote: 'https://static.wikia.nocookie.net/onepiece/images/a/a5/Charlotte_Compote_Anime_Infobox.png/revision/latest?cb=20230702183151',
  praline: 'https://static.wikia.nocookie.net/onepiece/images/1/11/Charlotte_Praline_Anime_Infobox.png/revision/latest?cb=20170528042923',
  giolla: 'https://static.wikia.nocookie.net/onepiece/images/2/21/Giolla_Anime_Infobox.png/revision/latest?cb=20221117034510',
  mansherry: 'https://static.wikia.nocookie.net/onepiece/images/5/54/Mansherry_Anime_Infobox.png/revision/latest?cb=20161221094836',
  scarlett: 'https://static.wikia.nocookie.net/onepiece/images/5/55/Scarlett_Anime_Infobox.png/revision/latest?cb=20141221160438',
  wanda: 'https://static.wikia.nocookie.net/onepiece/images/7/75/Wanda_Anime_Infobox.png/revision/latest?cb=20160829034647',
  porche: 'https://static.wikia.nocookie.net/onepiece/images/7/7e/Porche_Anime_Infobox.png/revision/latest?cb=20240523234723',
  whitey_bay: 'https://static.wikia.nocookie.net/onepiece/images/3/3b/Whitey_Bay_Anime_Infobox.png/revision/latest?cb=20210720203345',
  catarina_devon: 'https://static.wikia.nocookie.net/onepiece/images/4/4a/Catarina_Devon_Anime_Post_Timeskip_Infobox.png/revision/latest?cb=20200112041332',
  kozuki_toki: 'https://static.wikia.nocookie.net/onepiece/images/a/ad/Kouzuki_Toki_Anime_Infobox.png/revision/latest?cb=20240923154828',
  okiku: 'https://static.wikia.nocookie.net/onepiece/images/1/12/Kikunojo_Anime_Infobox.png/revision/latest?cb=20200620104530',
  shinobu: 'https://static.wikia.nocookie.net/onepiece/images/3/3f/Shinobu_Anime_Infobox.png/revision/latest?cb=20241015051553',
  otama: 'https://static.wikia.nocookie.net/onepiece/images/6/6d/Kurozumi_Tama_Anime_Infobox.png/revision/latest?cb=20210210051806',
  speed_smile: 'https://static.wikia.nocookie.net/onepiece/images/c/c1/Speed_Anime_Infobox.png/revision/latest?cb=20241110183728',
  belo_betty: 'https://static.wikia.nocookie.net/onepiece/images/d/dd/Belo_Betty_Anime_Infobox.png/revision/latest?cb=20240903112156',
  ain: 'https://static.wikia.nocookie.net/onepiece/images/6/64/Ain_Anime_Infobox.png/revision/latest?cb=20140622041350',
  carina: 'https://static.wikia.nocookie.net/onepiece/images/2/2c/Carina_Anime_Infobox.png/revision/latest?cb=20220714221036',
  ann_stampede: 'https://static.wikia.nocookie.net/onepiece/images/3/3d/Ann_Anime_Infobox.png/revision/latest?cb=20200407150603',
  vinsmoke_sora: 'https://static.wikia.nocookie.net/onepiece/images/4/4c/Vinsmoke_Sora_Anime_Infobox.png/revision/latest?cb=20190130220840',
  isuka: 'https://static.wikia.nocookie.net/onepiece/images/4/41/Isuka_Manga_Infobox.png/revision/latest?cb=20180305101925',
  dadan: 'https://static.wikia.nocookie.net/onepiece/images/b/b4/Curly_Dadan_Anime_Infobox.png/revision/latest?cb=20160802231340',
  ran_kuja: 'https://static.wikia.nocookie.net/onepiece/images/0/03/Ran_Anime_Infobox.png/revision/latest?cb=20091023200129',
  daisy_kuja: 'https://static.wikia.nocookie.net/onepiece/images/b/b7/Daisy_Anime_Infobox.png/revision/latest?cb=20130304220336',
  cosmos_kuja: 'https://static.wikia.nocookie.net/onepiece/images/b/bb/Cosmos_Anime_Infobox.png/revision/latest?cb=20090723231111',
  seira: 'https://static.wikia.nocookie.net/onepiece/images/e/e0/Seira_Anime_Infobox.png/revision/latest?cb=20140916073654',
  mero: 'https://static.wikia.nocookie.net/onepiece/images/5/55/Mero_Anime_Infobox.png/revision/latest?cb=20130720075238',
  citron: 'https://static.wikia.nocookie.net/onepiece/images/5/5b/Charlotte_Citron_Anime_Infobox.png/revision/latest?cb=20190203104804',
  cinnamon: 'https://static.wikia.nocookie.net/onepiece/images/d/dd/Charlotte_Cinnamon_Anime_Infobox.png/revision/latest?cb=20190203104624',
  mondee: 'https://static.wikia.nocookie.net/onepiece/images/b/bf/Charlotte_Mond%C3%A9e_Anime_Infobox.png/revision/latest?cb=20181028141559',
  poire: 'https://static.wikia.nocookie.net/onepiece/images/5/57/Charlotte_Poire_Anime_Infobox.png/revision/latest?cb=20200315062453',
  joscarpone: 'https://static.wikia.nocookie.net/onepiece/images/a/ae/Charlotte_Joscarpone_Anime_Infobox.png/revision/latest?cb=20171030014906',
  miss_monday: 'https://static.wikia.nocookie.net/onepiece/images/c/c1/Miss_Monday_Anime_Post_Timeskip_Infobox.png/revision/latest?cb=20251130161712',
  miss_fathersday: 'https://static.wikia.nocookie.net/onepiece/images/6/6c/Miss_Father%27s_Day_Anime_Infobox.png/revision/latest?cb=20221128165323',
  banchina: 'https://static.wikia.nocookie.net/onepiece/images/4/48/Banchina_Anime_Infobox.png/revision/latest?cb=20250717210954',
  lily_nefertari: 'https://static.wikia.nocookie.net/onepiece/images/a/a5/Nefertari_D._Lili_Anime_Infobox.png/revision/latest?cb=20240908021318',
  toko: 'https://static.wikia.nocookie.net/onepiece/images/0/0c/Toko_Anime_Infobox.png/revision/latest?cb=20200202102848',
  otoko: 'https://static.wikia.nocookie.net/onepiece/images/0/0c/Toko_Anime_Infobox.png/revision/latest?cb=20200202102848',
  aisa: 'https://static.wikia.nocookie.net/onepiece/images/4/4e/Aisa_Anime_Post_Timeskip_Infobox.png/revision/latest?cb=20251207162352',
  chimney: 'https://static.wikia.nocookie.net/onepiece/images/b/b3/Chimney_Manga_Post_Timeskip_Infobox.png/revision/latest?cb=20250318234329',
  jewelry_bonney_young: 'https://static.wikia.nocookie.net/onepiece/images/6/62/Jewelry_Bonney_Anime_Post_Timeskip_Infobox.png/revision/latest?cb=20230123001318',
  kureha: 'https://static.wikia.nocookie.net/onepiece/images/1/1b/Kureha_Anime_Infobox.png/revision/latest?cb=20150819163116'
};

app.get('/api/char-img/:id', (req, res) => {
  const id = req.params.id;
  const cacheFile = path.join(IMG_CACHE_DIR, `${id}.webp`);

  // Serve from cache if exists
  if (fs.existsSync(cacheFile)) {
    res.set('Content-Type', 'image/webp');
    res.set('Cache-Control', 'public, max-age=2592000');
    return fs.createReadStream(cacheFile).pipe(res);
  }

  const url = CHAR_IMAGES[id];
  if (!url) return res.status(404).send('Not found');

  https.get(url, { headers: { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)' } }, (proxyRes) => {
    if (proxyRes.statusCode >= 300 && proxyRes.statusCode < 400 && proxyRes.headers.location) {
      // Follow redirect
      https.get(proxyRes.headers.location, { headers: { 'User-Agent': 'Mozilla/5.0' } }, (finalRes) => {
        const contentType = finalRes.headers['content-type'] || 'image/webp';
        res.set('Content-Type', contentType);
        res.set('Cache-Control', 'public, max-age=2592000');
        const writeStream = fs.createWriteStream(cacheFile);
        finalRes.pipe(writeStream);
        finalRes.pipe(res);
      }).on('error', () => res.status(502).send('Proxy error'));
      return;
    }
    const contentType = proxyRes.headers['content-type'] || 'image/webp';
    res.set('Content-Type', contentType);
    res.set('Cache-Control', 'public, max-age=2592000');
    const writeStream = fs.createWriteStream(cacheFile);
    proxyRes.pipe(writeStream);
    proxyRes.pipe(res);
  }).on('error', () => res.status(502).send('Proxy error'));
});

// Load characters
const characters = JSON.parse(
  fs.readFileSync(path.join(__dirname, 'data/characters.json'), 'utf-8')
);

// In-memory chat history per session (simple approach)
const chatSessions = new Map();

// API: Get all characters (DB with JSON fallback)
app.get('/api/characters', (req, res) => {
  try {
    if (db) {
      const list = db.getCharacters();
      if (list && list.length > 0) return res.json(list);
    }
  } catch (err) {
    console.error('[Server] DB getCharacters failed, falling back to JSON:', err.message);
  }
  const list = characters.map(({ systemPrompt, ...c }) => c);
  res.json(list);
});

// API: Get single character
app.get('/api/characters/:id', (req, res) => {
  const char = characters.find((c) => c.id === req.params.id);
  if (!char) return res.status(404).json({ error: '角色不存在' });
  const { systemPrompt, ...safe } = char;
  res.json(safe);
});

// AI provider handlers
async function chatAnthropic(apiKey, systemPrompt, messages) {
  const client = new Anthropic.default({ apiKey });
  const response = await client.messages.create({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 1024,
    system: systemPrompt,
    messages,
  });
  return response.content[0].text;
}

async function chatOpenAI(apiKey, systemPrompt, messages) {
  const msgs = [{ role: 'system', content: systemPrompt }, ...messages];
  const data = await apiPost('https://api.openai.com/v1/chat/completions', {
    'Authorization': `Bearer ${apiKey}`,
  }, { model: 'gpt-4o', max_tokens: 1024, messages: msgs });
  if (data.error) throw new Error(data.error.message);
  return data.choices[0].message.content;
}

async function chatGemini(apiKey, systemPrompt, messages) {
  const contents = messages.map(m => ({
    role: m.role === 'assistant' ? 'model' : 'user',
    parts: [{ text: m.content }],
  }));
  const data = await apiPost(
    `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${apiKey}`,
    {},
    {
      system_instruction: { parts: [{ text: systemPrompt }] },
      contents,
      generationConfig: { maxOutputTokens: 1024 },
    }
  );
  if (data.error) throw new Error(data.error.message);
  return data.candidates[0].content.parts[0].text;
}

async function chatDeepSeek(apiKey, systemPrompt, messages) {
  const msgs = [{ role: 'system', content: systemPrompt }, ...messages];
  const data = await apiPost('https://api.deepseek.com/chat/completions', {
    'Authorization': `Bearer ${apiKey}`,
  }, { model: 'deepseek-chat', max_tokens: 1024, messages: msgs });
  if (data.error) throw new Error(data.error.message);
  return data.choices[0].message.content;
}

const AI_HANDLERS = {
  anthropic: chatAnthropic,
  openai: chatOpenAI,
  gemini: chatGemini,
  deepseek: chatDeepSeek,
};

// API: Chat with character
app.post('/api/chat', async (req, res) => {
  const { characterId, message, sessionId, apiKey, provider = 'anthropic' } = req.body;

  if (!characterId || !message) {
    return res.status(400).json({ error: '缺少参数' });
  }
  if (!apiKey) {
    return res.status(400).json({ error: '请设置 API Key' });
  }

  const handler = AI_HANDLERS[provider];
  if (!handler) {
    return res.status(400).json({ error: `不支持的 AI 模型: ${provider}` });
  }

  const char = characters.find((c) => c.id === characterId);
  if (!char) return res.status(404).json({ error: '角色不存在' });

  // Get or create session history
  const sid = sessionId || `${characterId}_${Date.now()}`;
  if (!chatSessions.has(sid)) {
    chatSessions.set(sid, []);
  }
  const history = chatSessions.get(sid);

  // Add user message
  history.push({ role: 'user', content: message });

  // Keep last 20 messages for context
  const recentHistory = history.slice(-20);

  try {
    const reply = await handler(apiKey, char.systemPrompt, recentHistory);

    // Add assistant reply to history
    history.push({ role: 'assistant', content: reply });

    // Persist messages to DB (non-blocking, failures don't affect response)
    try {
      if (db) {
        db.saveMessage(sid, characterId, 'user', message);
        db.saveMessage(sid, characterId, 'assistant', reply);
      }
    } catch (dbErr) {
      console.error('[Server] DB saveMessage failed:', dbErr.message);
    }

    res.json({
      reply,
      sessionId: sid,
    });
  } catch (err) {
    // Remove failed user message
    history.pop();
    console.error('Chat error:', err.message);
    res.status(500).json({ error: err.message || 'AI 回复失败' });
  }
});

// API: Clear chat history
app.post('/api/chat/clear', (req, res) => {
  const { sessionId } = req.body;
  if (sessionId) chatSessions.delete(sessionId);
  res.json({ ok: true });
});

// API: Toggle like on a story
app.post('/api/stories/like', (req, res) => {
  const { storyId } = req.body;
  if (!storyId) return res.status(400).json({ error: '缺少 storyId' });
  try {
    if (!db) return res.status(503).json({ error: '数据库不可用' });
    const result = db.toggleLike(storyId);
    const count = db.getStoryLikes(storyId);
    res.json({ ...result, count });
  } catch (err) {
    console.error('[Server] toggleLike failed:', err.message);
    res.status(500).json({ error: '操作失败' });
  }
});

// API: Get like count for a story
app.get('/api/stories/:id/likes', (req, res) => {
  try {
    if (!db) return res.status(503).json({ error: '数据库不可用' });
    const count = db.getStoryLikes(req.params.id);
    res.json({ storyId: req.params.id, count });
  } catch (err) {
    console.error('[Server] getStoryLikes failed:', err.message);
    res.status(500).json({ error: '获取失败' });
  }
});

// ===== Subtitle Tool =====
const subtitleRouter = require('./tools/subtitle/router');
app.use('/subtitle', subtitleRouter);
// Serve subtitle page
app.get('/subtitle', (req, res) => {
  res.sendFile(path.join(__dirname, 'tools/subtitle/index.html'));
});

// ===== Clipper Tool =====
const clipperRouter = require('./tools/clipper/router');
app.use('/clipper', clipperRouter);
app.get('/clipper', (req, res) => {
  res.sendFile(path.join(__dirname, 'tools/clipper/index.html'));
});

// ===== Live Relay Tool =====
const liveRouter = require('./tools/live/router');
app.use('/live', liveRouter);
app.get('/live', (req, res) => {
  res.sendFile(path.join(__dirname, 'tools/live/index.html'));
});

app.listen(PORT, () => {
  console.log(`Anime Chat running at http://localhost:${PORT}`);
});
