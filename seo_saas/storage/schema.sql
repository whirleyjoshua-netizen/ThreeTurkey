CREATE TABLE IF NOT EXISTS waitlist (
    id          SERIAL PRIMARY KEY,
    email       TEXT NOT NULL UNIQUE,
    company     TEXT,
    website     TEXT,
    monthly_traffic TEXT,
    referral    TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);
