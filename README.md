# Simple Voting App

This is a distributed, polyglot voting application built using a microservices architecture. It allows users to log in via Google OAuth, securely cast a vote for a candidate, and view real-time results on a live dashboard.

## 🏗️ Architecture & Data Flow

The application is broken down into modular components that handle specific responsibilities, simulating a highly scalable enterprise architecture.

1. **Voting App (Python/Flask)**
   - Serves as the user-facing frontend.
   - Handles Google OAuth authentication.
   - Enforces the rule that users can only vote once by checking a Redis `Set` (`voted_users`).
   - Pushes successful votes as a JSON payload to a Redis `List` queue (`votes`).
   - Exposes a `/api/results` endpoint that reads the live tally from Postgres for the Results dashboard.
   - Exposes a `/reset` endpoint to easily wipe all sessions and votes for testing.

2. **Results App (React/Vite)**
   - A single-page application (SPA) dashboard built with React.
   - Periodically polls the Flask `/api/results` endpoint (every 5 minutes) or allows manual refresh.
   - Displays the current vote tally dynamically.

3. **Background Worker (C# / .NET)**
   - Continuously polls the Redis `votes` queue for new data using a non-blocking `ListLeftPop`.
   - Deserializes the JSON payload and securely inserts the vote into the PostgreSQL database.
   - Handles transient database errors and duplicate votes by routing failed payloads to a Dead Letter Queue (`votes_dlq`) in Redis to ensure zero data loss.

4. **Queue & Session Store (Redis)**
   - **(New!) Redis Streams:** We recently transitioned from basic Redis Lists to **Redis Streams** for the voting queue. This introduces Consumer Groups and explicit Acknowledgments (ACK). If the C# worker crashes mid-processing, the unacknowledged vote remains in the Pending Entries List (PEL) and is recovered upon restart, guaranteeing **zero data loss** (at-least-once delivery).
   - Acts as an intermediary message broker, decoupling the Flask frontend from the PostgreSQL database to absorb high-traffic spikes without crashing the DB.
   - Acts as an ultra-fast in-memory lookup table to check if a user has already voted.

5. **Database (PostgreSQL) & CQRS Scaling**
   - The permanent, persistent ledger for the application.
   - Stores the `candidates` table and the immutable `votes` table.
   - Enforces data integrity at the database layer (e.g., unique constraints on `user_email`).
   - **(New!) CQRS Pattern:** The database implements a Command Query Responsibility Segregation (CQRS) pattern. The C# worker transactionally saves the raw vote (for auditing) *and* increments a pre-aggregated `vote_count` directly on the `candidates` table. This allows the Results API to fetch live totals instantly in `O(1)` time without running expensive `COUNT()` aggregations over millions of rows.

---

## ⚙️ Prerequisites

Ensure you have the following installed on your machine:
- **Homebrew** (for Mac users)
- **Python 3.x**
- **Node.js & npm** (for the React app)
- **.NET SDK** (for the C# worker)
- **PostgreSQL & Redis** (can be installed via Homebrew)
- **GitHub CLI (`gh`)** (optional, for repo management)

---

## 🛠 Setup (First Time Only)

**1. Environment Variables**
Copy the example environment file and fill in your secrets (like your Google OAuth credentials):
```bash
cp .env.example .env
```
*(Note: If you installed PostgreSQL via Homebrew, `PG_USER` is typically your Mac username, not `postgres`. This is pre-configured in `.env.example`.)*

**2. Install Python Dependencies**
```bash
cd VotingApp
pip install -r requirements.txt
cd ..
```

**3. Install React Dependencies**
```bash
cd ResultsApp
npm install
cd ..
```

**4. Initialize the Database**
Make sure PostgreSQL is running, then seed the database with tables and candidates:
```bash
brew services start postgresql
python3 Postgres/init_db.py
```

---

## 🚀 How to Start the Application

We have included helper Bash scripts to effortlessly start and stop the entire microservices stack.

To start everything, simply run:
```bash
./start.sh
```
This script will:
1. Start Redis and PostgreSQL background services.
2. Start the Flask App, the C# Worker, and the React App in the background.
3. Save the process IDs and stream logs to `flask.log`, `worker.log`, and `react.log`.

**Access the applications:**
- 👉 **Voting App:** [http://127.0.0.1:5000](http://127.0.0.1:5000)
- 👉 **Results Dashboard:** [http://localhost:5173](http://localhost:5173)

### Resetting Votes
To start fresh, visit [http://127.0.0.1:5000/reset](http://127.0.0.1:5000/reset) to clear all Redis sessions and truncate the PostgreSQL votes table.

---

## 🛑 How to Shut Down Safely

When you are done testing, you must shut down the background processes gracefully to avoid port conflicts and memory leaks.

Simply run:
```bash
./stop.sh
```
This script will:
1. Kill the Flask, React, and .NET processes.
2. Flush the Redis cache to wipe stale sessions.
3. Stop the Redis and PostgreSQL background services.
