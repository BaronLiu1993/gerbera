CREATE TABLE IF NOT EXISTS events_log (
    id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    event_type TEXT NOT NULL,
    source_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    aggregate_id TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS events_timestamp_idx
ON events_log(timestamp);
