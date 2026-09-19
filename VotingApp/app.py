import json
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
from authlib.integrations.flask_client import OAuth
from flask import Flask, redirect, render_template, request, session, url_for, jsonify
import redis
import psycopg2
from psycopg2 import pool
import getpass

app = Flask(__name__)

# Required for session management (keep this secure/random in production)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))

# Initialize Redis Client (connecting to local Redis on port 6379)
redis_client = redis.Redis(host=os.environ.get("REDIS_HOST", "localhost"), port=int(os.environ.get("REDIS_PORT", 6379)), decode_responses=True)

# PostgreSQL connection helper function
# Initialize database connection pool
try:
    db_pool = psycopg2.pool.SimpleConnectionPool(
        1, 10,
        host=os.environ.get("PG_HOST", "localhost"),
        database=os.environ.get("PG_DATABASE", "voting"),
        user=os.environ.get("PG_USER", getpass.getuser()),
        password=os.environ.get("PG_PASSWORD", "")
    )
except psycopg2.Error as e:
    print(f"Error initializing connection pool: {e}")
    db_pool = None

def get_db_connection():
    if db_pool:
        return db_pool.getconn()
    return None

def release_db_connection(conn):
    if db_pool and conn:
        db_pool.putconn(conn)

# Configure OAuth
oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID", "YOUR_GOOGLE_CLIENT_ID_HERE"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", "YOUR_GOOGLE_CLIENT_SECRET_HERE"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    # server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

@app.route("/")
def index():
  if "user" in session:
    user = session["user"]
    return (
        f"Hello, {user['name']} ({user['email']})! <br><a"
        f" href='/vote'>Go to Voting</a> | <a href='/logout'>Logout</a>"
    )
  return "Welcome! Please <a href='/login'>Login with Google</a>"


@app.route("/login")
def login():
  redirect_uri = url_for("authorize", _external=True)
  return google.authorize_redirect(redirect_uri)


@app.route("/authorize")
def authorize():
  token = google.authorize_access_token()
  user_info = google.parse_id_token(token, None)
  session["user"] = {
      "name": user_info.get("name"),
      "email": user_info.get("email"),
  }
  return redirect(url_for("index"))


@app.route("/logout")
def logout():
  session.pop("user", None)
  return redirect(url_for("index"))


@app.route("/vote")
def vote():
  if "user" not in session:
    return redirect(url_for("login"))

  user_email = session["user"]["email"]

  # Enforce single vote check via Redis
  if redis_client.sismember("voted_users", user_email):
    return "<h3>You have already cast your vote!</h3><a href='/logout'>Logout</a>"

  # Fetch candidates directly from PostgreSQL using connection pool
  conn = get_db_connection()
  candidates = []
  if conn:
      try:
          cur = conn.cursor()
          cur.execute("SELECT id, name FROM candidates;")
          candidates = cur.fetchall()
          cur.close()
      finally:
          release_db_connection(conn)

  html = "<h2>Vote for your favorite cricketer:</h2><form action='/submit-vote' method='POST'>"
  for c in candidates:
    candidate_id, candidate_name = c
    html += (
        f"<label><input type='radio' name='candidate_id' value='{candidate_id}'"
        f" required> {candidate_name}</label><br>"
    )
  html += "<br><button type='submit'>Submit Vote</button></form>"
  return html


@app.route("/submit-vote", methods=["POST"])
def submit_vote():
  if "user" not in session:
    return redirect(url_for("login"))

  user_email = session["user"]["email"]

  candidate_id = request.form.get("candidate_id")
  vote_data = {"user_email": user_email, "candidate_id": int(candidate_id)}

  # Use pipeline for atomic SADD and RPUSH
  pipeline = redis_client.pipeline()
  pipeline.sadd("voted_users", user_email)
  pipeline.xadd('votes', {'payload': json.dumps(vote_data)})
  results = pipeline.execute()

  # SADD returns 1 if added, 0 if already exists
  if results[0] == 0:
    return "You have already voted!"


  return "<h3>Vote successfully cast and pushed to the queue!</h3><a href='/'>Home</a>"



@app.route("/api/results")
def api_results():
  conn = get_db_connection()
  if conn:
    try:
      cur = conn.cursor()
      cur.execute('''
          SELECT name, vote_count as votes 
          FROM candidates 
          ORDER BY votes DESC;
      ''')
      results = [{"name": row[0], "votes": row[1]} for row in cur.fetchall()]
      cur.close()
      
      # Add CORS headers so React app running on different port can access it
      response = jsonify(results)
      response.headers.add("Access-Control-Allow-Origin", "*")
      return response
    finally:
      release_db_connection(conn)
  return jsonify({"error": "Database connection failed"}), 500


@app.route("/reset")
def reset():
  # Clear Redis queues and tracking sets
  redis_client.delete("voted_users")
  redis_client.delete("votes")
  redis_client.delete("votes_dlq")
  try:
      # Re-create consumer group on reset
      redis_client.xgroup_create("votes", "worker-group", id="0", mkstream=True)
  except Exception:
      pass
  
  # Clear Postgres voting records
  conn = get_db_connection()
  if conn:
    try:
      cur = conn.cursor()
      cur.execute("TRUNCATE TABLE votes; UPDATE candidates SET vote_count = 0;")
      conn.commit()
      cur.close()
    finally:
      release_db_connection(conn)
      
  return "<h3>All voting records and sessions have been cleared successfully!</h3><a href='/'>Go Home</a>"

if __name__ == "__main__":

  app.run(debug=True)