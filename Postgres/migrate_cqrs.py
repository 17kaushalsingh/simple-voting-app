import os
import getpass
import psycopg2
import sys

# We need to manually load dotenv here if we are running from start.sh in the root
from dotenv import load_dotenv
load_dotenv(".env")

try:
    conn = psycopg2.connect(
        host=os.environ.get("PG_HOST", "localhost"),
        database=os.environ.get("PG_DATABASE", "voting"),
        user=os.environ.get("PG_USER", getpass.getuser()),
        password=os.environ.get("PG_PASSWORD", "")
    )
    conn.autocommit = True
    cur = conn.cursor()
    
    cur.execute("""
    DO $$ 
    BEGIN 
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name='candidates' AND column_name='vote_count') THEN 
            ALTER TABLE candidates ADD COLUMN vote_count INT DEFAULT 0; 
        END IF; 
    END $$;
    """)
    
    cur.execute("""
    UPDATE candidates c
    SET vote_count = (
        SELECT COUNT(*) FROM votes v WHERE v.candidate_id = c.id
    );
    """)
    
    cur.close()
    conn.close()
    print("Database schema successfully migrated for CQRS!")
except Exception as e:
    print(f"Migration error: {e}")
