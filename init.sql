CREATE TABLE IF NOT EXISTS lessons (
    lesson_id TEXT PRIMARY KEY,
    user_id TEXT,
    datetime TIMESTAMP,  -- Use TIMESTAMP for date-time values
    sport TEXT NOT NULL,
    trainer TEXT,
    message_sent BOOLEAN,
    response TEXT,
    UNIQUE (sport, datetime, user_id)
);

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    sign_up_date TIMESTAMP NOT NULL DEFAULT NOW(),  -- Use NOW() for current timestamp
    login_method TEXT NOT NULL,
    sport TEXT,
    username TEXT,
    password TEXT, -- Note to user: Hash your passwords before saving please
    telegram_id BIGINT
);
