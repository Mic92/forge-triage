CREATE TABLE IF NOT EXISTS notifications (
    notification_id   TEXT PRIMARY KEY,
    repo_owner        TEXT NOT NULL,
    repo_name         TEXT NOT NULL,
    subject_type      TEXT NOT NULL,
    subject_title     TEXT NOT NULL,
    subject_url       TEXT,
    html_url          TEXT,
    reason            TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    unread            INTEGER NOT NULL DEFAULT 1,
    priority_score    INTEGER NOT NULL DEFAULT 0,
    priority_tier     TEXT NOT NULL DEFAULT 'fyi',
    raw_json          TEXT NOT NULL,
    comments_loaded   INTEGER NOT NULL DEFAULT 0,
    last_viewed_at    TEXT,
    ci_status         TEXT,
    subject_state     TEXT
);

CREATE TABLE IF NOT EXISTS comments (
    comment_id        TEXT PRIMARY KEY,
    notification_id   TEXT NOT NULL
        REFERENCES notifications(notification_id) ON DELETE CASCADE,
    author            TEXT NOT NULL,
    body              TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_notifications_priority
    ON notifications(priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_repo
    ON notifications(repo_owner, repo_name);
CREATE INDEX IF NOT EXISTS idx_comments_notification
    ON comments(notification_id, created_at);
