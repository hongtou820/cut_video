const express = require('express');
const path = require('path');
const clipperRouter = require('./router');

const app = express();
const PORT = 1235;

// Clipper routes first
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});
app.use('/clipper', clipperRouter);
app.get('/clipper', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

// Only serve CSS from public
app.use('/css', express.static(path.join(__dirname, '../../public/css')));

app.listen(PORT, () => {
  console.log(`Clipper running at http://localhost:${PORT}`);
});
