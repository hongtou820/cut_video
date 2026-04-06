const Database = require('better-sqlite3');
const fs = require('fs');
const path = require('path');

const DB_DIR = path.join(__dirname, 'data');
const DB_PATH = path.join(DB_DIR, 'ciyuanchat.db');
const CHARACTERS_JSON = path.join(__dirname, 'data/characters.json');

let db;

function getDB() {
  if (!db) {
    if (!fs.existsSync(DB_DIR)) fs.mkdirSync(DB_DIR, { recursive: true });
    db = new Database(DB_PATH);
    db.pragma('journal_mode = WAL');
    db.pragma('foreign_keys = ON');
  }
  return db;
}

function initDB() {
  const conn = getDB();

  conn.exec(`
    CREATE TABLE IF NOT EXISTS characters (
      id TEXT PRIMARY KEY,
      name TEXT,
      fullName TEXT,
      title TEXT,
      gender TEXT,
      image TEXT,
      color TEXT,
      gradient TEXT,
      tags TEXT,
      greeting TEXT,
      description TEXT,
      systemPrompt TEXT
    );

    CREATE TABLE IF NOT EXISTS chat_sessions (
      id TEXT PRIMARY KEY,
      character_id TEXT,
      created_at TEXT DEFAULT (datetime('now')),
      updated_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS chat_messages (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      session_id TEXT,
      role TEXT,
      content TEXT,
      created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS user_settings (
      key TEXT PRIMARY KEY,
      value TEXT
    );

    CREATE TABLE IF NOT EXISTS story_likes (
      story_id TEXT,
      user_id TEXT DEFAULT 'anonymous',
      created_at TEXT DEFAULT (datetime('now')),
      PRIMARY KEY (story_id, user_id)
    );

    CREATE TABLE IF NOT EXISTS stories (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      char_id TEXT,
      category TEXT,
      scene TEXT,
      text TEXT,
      tags TEXT,
      created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
    CREATE INDEX IF NOT EXISTS idx_chat_sessions_character ON chat_sessions(character_id);
    CREATE INDEX IF NOT EXISTS idx_stories_char ON stories(char_id);
  `);

  // Import characters from JSON on first run (if table is empty)
  try {
    const count = conn.prepare('SELECT COUNT(*) as cnt FROM characters').get();
    if (count.cnt === 0 && fs.existsSync(CHARACTERS_JSON)) {
      const characters = JSON.parse(fs.readFileSync(CHARACTERS_JSON, 'utf-8'));
      const insert = conn.prepare(`
        INSERT OR IGNORE INTO characters (id, name, fullName, title, gender, image, color, gradient, tags, greeting, description, systemPrompt)
        VALUES (@id, @name, @fullName, @title, @gender, @image, @color, @gradient, @tags, @greeting, @description, @systemPrompt)
      `);

      const insertMany = conn.transaction((chars) => {
        for (const char of chars) {
          insert.run({
            id: char.id,
            name: char.name || '',
            fullName: char.fullName || '',
            title: char.title || '',
            gender: char.gender || '',
            image: char.image || '',
            color: char.color || '',
            gradient: char.gradient || '',
            tags: JSON.stringify(char.tags || []),
            greeting: char.greeting || '',
            description: char.description || '',
            systemPrompt: char.systemPrompt || '',
          });
        }
      });

      insertMany(characters);
      console.log(`[DB] Imported ${characters.length} characters from characters.json`);
    }
  } catch (err) {
    console.error('[DB] Error importing characters:', err.message);
  }

  console.log('[DB] Database initialized at', DB_PATH);
}

function getCharacters() {
  const conn = getDB();
  const rows = conn.prepare(
    'SELECT id, name, fullName, title, gender, image, color, gradient, tags, greeting, description FROM characters'
  ).all();
  return rows.map((row) => ({
    ...row,
    tags: JSON.parse(row.tags || '[]'),
  }));
}

function getCharacter(id) {
  const conn = getDB();
  const row = conn.prepare('SELECT * FROM characters WHERE id = ?').get(id);
  if (!row) return null;
  return {
    ...row,
    tags: JSON.parse(row.tags || '[]'),
  };
}

function saveMessage(sessionId, characterId, role, content) {
  const conn = getDB();

  // Ensure session exists
  const upsertSession = conn.prepare(`
    INSERT INTO chat_sessions (id, character_id, updated_at)
    VALUES (?, ?, datetime('now'))
    ON CONFLICT(id) DO UPDATE SET updated_at = datetime('now')
  `);
  upsertSession.run(sessionId, characterId);

  // Insert message
  const insertMsg = conn.prepare(
    'INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)'
  );
  insertMsg.run(sessionId, role, content);
}

function getSessionMessages(sessionId, limit = 50) {
  const conn = getDB();
  const rows = conn.prepare(
    'SELECT role, content, created_at FROM chat_messages WHERE session_id = ? ORDER BY id DESC LIMIT ?'
  ).all(sessionId, limit);
  return rows.reverse();
}

function toggleLike(storyId, userId = 'anonymous') {
  const conn = getDB();
  const existing = conn.prepare(
    'SELECT 1 FROM story_likes WHERE story_id = ? AND user_id = ?'
  ).get(storyId, userId);

  if (existing) {
    conn.prepare('DELETE FROM story_likes WHERE story_id = ? AND user_id = ?').run(storyId, userId);
    return { liked: false };
  } else {
    conn.prepare('INSERT INTO story_likes (story_id, user_id) VALUES (?, ?)').run(storyId, userId);
    return { liked: true };
  }
}

function getStoryLikes(storyId) {
  const conn = getDB();
  const row = conn.prepare(
    'SELECT COUNT(*) as count FROM story_likes WHERE story_id = ?'
  ).get(storyId);
  return row.count;
}

module.exports = {
  initDB,
  getCharacters,
  getCharacter,
  saveMessage,
  getSessionMessages,
  toggleLike,
  getStoryLikes,
};
