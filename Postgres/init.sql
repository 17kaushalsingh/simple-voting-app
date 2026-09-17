-- Drop tables if they already exist (clean reset)
DROP TABLE IF EXISTS votes;
DROP TABLE IF EXISTS candidates;

-- 1. Create the candidates table
CREATE TABLE candidates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL
);

-- 2. Create the votes event ledger table with unique email constraint
CREATE TABLE votes (
    id SERIAL PRIMARY KEY,
    candidate_id INT REFERENCES candidates(id) ON DELETE CASCADE,
    user_email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Insert sample candidates
INSERT INTO candidates (name) VALUES 
    ('Virat Kohli'),
    ('MS Dhoni'),
    ('Rohit Sharma');