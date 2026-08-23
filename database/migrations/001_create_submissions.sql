CREATE TABLE IF NOT EXISTS submissions (
  id UUID PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  address VARCHAR(250) NOT NULL,
  age INTEGER NOT NULL CHECK (age BETWEEN 0 AND 120),
  archive_status VARCHAR(20) NOT NULL DEFAULT 'pending',
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_submissions_created_at ON submissions (created_at);
CREATE INDEX IF NOT EXISTS idx_submissions_archive_pending
  ON submissions (archive_status) WHERE archive_status = 'pending';
