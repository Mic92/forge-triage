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

CREATE TABLE IF NOT EXISTS pr_details (
    notification_id   TEXT PRIMARY KEY
        REFERENCES notifications(notification_id) ON DELETE CASCADE,
    pr_number         INTEGER NOT NULL,
    author            TEXT NOT NULL,
    body              TEXT,
    labels_json       TEXT NOT NULL DEFAULT '[]',
    base_ref          TEXT,
    head_ref          TEXT,
    loaded_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS pr_reviews (
    review_id         TEXT PRIMARY KEY,
    notification_id   TEXT NOT NULL
        REFERENCES notifications(notification_id) ON DELETE CASCADE,
    author            TEXT NOT NULL,
    state             TEXT NOT NULL,
    body              TEXT,
    submitted_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_comments (
    comment_id        TEXT PRIMARY KEY,
    review_id         TEXT
        REFERENCES pr_reviews(review_id) ON DELETE CASCADE,
    notification_id   TEXT NOT NULL
        REFERENCES notifications(notification_id) ON DELETE CASCADE,
    thread_id         TEXT,
    author            TEXT NOT NULL,
    body              TEXT NOT NULL,
    path              TEXT,
    diff_hunk         TEXT,
    line              INTEGER,
    side              TEXT,
    in_reply_to_id    TEXT,
    is_resolved       INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pr_files (
    file_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    notification_id   TEXT NOT NULL
        REFERENCES notifications(notification_id) ON DELETE CASCADE,
    filename          TEXT NOT NULL,
    status            TEXT NOT NULL,
    additions         INTEGER NOT NULL DEFAULT 0,
    deletions         INTEGER NOT NULL DEFAULT 0,
    patch             TEXT
);

CREATE INDEX IF NOT EXISTS idx_notifications_priority
    ON notifications(priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_repo
    ON notifications(repo_owner, repo_name);
CREATE INDEX IF NOT EXISTS idx_comments_notification
    ON comments(notification_id, created_at);
CREATE INDEX IF NOT EXISTS idx_review_comments_notification
    ON review_comments(notification_id, created_at);
CREATE INDEX IF NOT EXISTS idx_pr_files_notification
    ON pr_files(notification_id);
