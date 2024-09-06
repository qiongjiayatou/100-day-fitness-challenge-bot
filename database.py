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
            # Drop the existing users table if it exists
            # cur.execute("DROP TABLE IF EXISTS users CASCADE")
            
            # Recreate the users table
            # cur.execute("""
            #     CREATE TABLE users (
            #         id SERIAL PRIMARY KEY,
            #         telegram_id BIGINT UNIQUE NOT NULL,
            #         username VARCHAR(255),
            #         first_name VARCHAR(255),
            #         last_name VARCHAR(255),
            #         is_admin BOOLEAN DEFAULT FALSE,
            #         password VARCHAR(255) NOT NULL,
            #         is_authenticated BOOLEAN DEFAULT FALSE,
            #         created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            #         last_login TIMESTAMP WITH TIME ZONE
            #     )
            # """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS activities (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT REFERENCES users(telegram_id),
                    activity_name VARCHAR(255) NOT NULL,
                    reps_or_duration VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
        conn.commit()
    finally:
        release_connection(conn)

# Export the db_pool as db
db = db_pool

# Add more database operations as needed