-- Mini Social Platform schema + seed。
-- 跟先前 in-memory 假資料同形狀：50 users / 200 posts。

CREATE TABLE users (
    id           int PRIMARY KEY,
    username     text NOT NULL UNIQUE,
    display_name text NOT NULL
);

CREATE TABLE posts (
    id        int PRIMARY KEY,
    author_id int  NOT NULL REFERENCES users (id),
    content   text NOT NULL,
    likes     int  NOT NULL DEFAULT 0
);

CREATE TABLE messages (
    id           bigserial PRIMARY KEY,
    sender_id    int  NOT NULL REFERENCES users (id),
    recipient_id int  NOT NULL REFERENCES users (id),
    content      text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now()
);

INSERT INTO users (id, username, display_name)
SELECT i, 'user' || i, 'User ' || i
FROM generate_series(1, 50) AS i;

INSERT INTO posts (id, author_id, content, likes)
SELECT i, (i % 50) + 1, 'Post #' || i || ' — hello world', i * 3 % 17
FROM generate_series(1, 200) AS i;
