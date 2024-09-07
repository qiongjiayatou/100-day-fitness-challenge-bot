import psycopg2
from psycopg2 import pool
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

# Create a connection pool
db_pool = pool.SimpleConnectionPool(
    1, 20,
    host=DB_HOST,
    port=DB_PORT,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

def get_connection():
    return db_pool.getconn()

def release_connection(conn):
    db_pool.putconn(conn)

def init_db():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Create the users table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE NOT NULL,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    last_name VARCHAR(255),
                    is_admin BOOLEAN DEFAULT FALSE,
                    password VARCHAR(255) NOT NULL,
                    is_authenticated BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP WITH TIME ZONE
                )
            """)
            
            # Create the reference_activities table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS reference_activities (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(id),
                    activity_name TEXT NOT NULL,
                    UNIQUE (user_id, activity_name)
                )
            """)
            
            # Create the activities table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS activities (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(id),
                    reference_activity_id INTEGER REFERENCES reference_activities(id),
                    reps_or_duration VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Add an index for faster queries on activities table
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_activities_reference_activity_id 
                ON activities(reference_activity_id)
            """)
            
            conn.commit()
    finally:
        release_connection(conn)

# Export the db_pool as db
db = db_pool

def migrate_to_user_id():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            with open('migration_scripts.sql', 'r') as file:
                sql_script = file.read()
                cur.execute(sql_script)
            conn.commit()
            print("Migration completed successfully.")
    except Exception as e:
        conn.rollback()
        print(f"Error during migration: {e}")
    finally:
        release_connection(conn)

# Add more database operations as needed