-- The tracer's data model. Plant structure, the knowledge graph and clean time series live in one SQLite file.

-- the line as commissioned
CREATE TABLE IF NOT EXISTS assets (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  name TEXT NOT NULL,
  position INTEGER NOT NULL            -- place in the material flow, 0 = first machine
);
CREATE TABLE IF NOT EXISTS flow (
  src TEXT NOT NULL REFERENCES assets(id),
  dst TEXT NOT NULL REFERENCES assets(id),
  PRIMARY KEY (src, dst)
);
CREATE TABLE IF NOT EXISTS signals (
  id TEXT PRIMARY KEY,                 -- canonical id, e.g. F1.fill_pressure
  asset TEXT NOT NULL REFERENCES assets(id),
  unit TEXT NOT NULL,
  lo REAL NOT NULL,
  hi REAL NOT NULL
);

-- what devices call a signal, and who said so
CREATE TABLE IF NOT EXISTS aliases (
  tag TEXT PRIMARY KEY,
  signal TEXT NOT NULL REFERENCES signals(id),
  source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quarantine (
  tag TEXT PRIMARY KEY,
  messages INTEGER NOT NULL,
  first_seen REAL NOT NULL,
  suggestion TEXT                      -- a proposed signal; a person decides
);

-- clean samples on the line's clock
CREATE TABLE IF NOT EXISTS samples (
  signal TEXT NOT NULL REFERENCES signals(id),
  ts REAL NOT NULL,                    -- when it was measured, corrected to the line's clock
  value REAL,                          -- NULL when the reading is not usable
  recv_ts REAL NOT NULL,               -- first time the backend had it
  quality TEXT NOT NULL,               -- ok, converted:<unit>, invalid:sentinel, invalid:range, stuck
  PRIMARY KEY (signal, ts)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS samples_recv ON samples(recv_ts);

CREATE TABLE IF NOT EXISTS device_clock (
  device TEXT PRIMARY KEY REFERENCES assets(id),
  offset_s REAL NOT NULL,              -- device clock minus line clock
  heartbeats INTEGER NOT NULL,
  applied INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS gaps (
  signal TEXT NOT NULL REFERENCES signals(id),
  start REAL NOT NULL,
  stop REAL NOT NULL,
  PRIMARY KEY (signal, start)
);
CREATE TABLE IF NOT EXISTS alarms (
  code TEXT NOT NULL,
  asset TEXT NOT NULL REFERENCES assets(id),
  ts REAL NOT NULL,
  recv_ts REAL NOT NULL,
  text TEXT NOT NULL,
  PRIMARY KEY (code, ts)
);

-- the knowledge graph: documents, what they mention, which version replaced which
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,                  -- manual, ticket
  title TEXT NOT NULL,
  text TEXT NOT NULL,
  asset TEXT,
  version INTEGER,
  written TEXT,
  superseded_by TEXT REFERENCES documents(id),
  source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mentions (
  doc TEXT NOT NULL REFERENCES documents(id),
  entity TEXT NOT NULL,                -- an asset id or an alarm code
  PRIMARY KEY (doc, entity)
);

-- tickets the assistant opened, and who asked
CREATE TABLE IF NOT EXISTS opened_tickets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  asset TEXT NOT NULL REFERENCES assets(id),
  summary TEXT NOT NULL,
  requested_by TEXT NOT NULL,
  ts REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS ingest_counts (
  name TEXT PRIMARY KEY,
  n INTEGER NOT NULL
);
