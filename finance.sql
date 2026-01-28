CREATE TABLE transactions (
    'user_id' INTEGER,
    'symbol' TEXT,
    'shares' INTEGER,
    'current_price' REAL,
    'total_price' REAL,
    'balance' REAL,
    'date' TIMESTAMP,
    'method' TEXT
);

CREATE TABLE portofolio (
    'user_id' INTEGER,
    'symbol' TEXT,
    'shares' INTEGER,
    'price' REAL,
    'total' REAL
);

SELECT * FROM users;
DELETE FROM users where id = 11;
SELECT symbol FROM transactions WHERE user_id = 13;