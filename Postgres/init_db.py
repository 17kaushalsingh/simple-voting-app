import getpass
import psycopg2


def initialize_database():
  # Get your Mac's current username (e.g., 'kaushalsingh')
  db_user = getpass.getuser()

  # 1. Connect to the default 'postgres' system database using your Mac username
  conn = psycopg2.connect(
      host="localhost", database="postgres", user=db_user, password=""
  )
  conn.autocommit = True
  cur = conn.cursor()

  cur.execute("SELECT 1 FROM pg_database WHERE datname = 'voting'")
  if not cur.fetchone():
    cur.execute("CREATE DATABASE voting;")
    print("Database 'voting' created.")
  else:
    print("Database 'voting' already exists.")

  cur.close()
  conn.close()

  # 2. Connect to the 'voting' database and run init.sql
  conn = psycopg2.connect(
      host="localhost", database="voting", user=db_user, password=""
  )
  cur = conn.cursor()

  with open("init.sql", "r") as f:
    sql_script = f.read()

  cur.execute(sql_script)
  conn.commit()

  cur.close()
  conn.close()
  print("Schema created and database seeded successfully!")


if __name__ == "__main__":
  initialize_database()