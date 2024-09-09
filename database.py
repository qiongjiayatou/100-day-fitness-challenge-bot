import psycopg2
from psycopg2 import pool
from config import POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD

# Create a connection pool
db_pool = pool.SimpleConnectionPool(
    1, 20,
    host=POSTGRES_HOST,
    port=POSTGRES_PORT,
    dbname=POSTGRES_DB,
    user=POSTGRES_USER,
    password=POSTGRES_PASSWORD
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
                    user_id INTEGER REFERENCES users(id),
                    activity_name TEXT NOT NULL,
                    activity_type VARCHAR(50) NOT NULL,
                    UNIQUE (user_id, activity_name)
                )
            """)
            
            # Create the activities table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS activities (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    reference_activity_id INTEGER REFERENCES reference_activities(id),
                    value BIGINT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Add an index for faster queries on activities table
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_activities_reference_activity_id 
                ON activities(reference_activity_id)
            """)
            
            # Check if initial data has already been inserted
            cur.execute("SELECT COUNT(*) FROM users")
            user_count = cur.fetchone()[0]
            
            if user_count == 0:
                # Insert initial data only if the users table is empty
                cur.execute("""
                    INSERT INTO users (id, telegram_id, username, first_name, last_name, is_admin, password, is_authenticated, created_at, last_login)
                    VALUES 
                    (1, 5238316166, NULL, NULL, NULL, FALSE, '$2b$12$V92Cf8f0F3CzyHXWHZA7e.PnQrz9C7OsaLErTT.fUvUDQjTPG0DbO', TRUE, '2024-09-06 13:40:08.745742+00', NULL),
                    (2, 1509754664, NULL, NULL, NULL, FALSE, '$2b$12$TzOkohb.ua.zNZxrQwTrIOM20qFJNeonzsit/r3VVTfMSybJVKuhS', TRUE, '2024-09-06 21:06:59.388182+00', NULL),
                    (3, 473767479, NULL, NULL, NULL, FALSE, '$2b$12$UgsHEdq6KvRwNUK7CYheauW.rlmMVG1xBvLaqfOYJqjvDCA1jc11K', TRUE, '2024-09-07 12:11:53.550141+00', NULL),
                    (4, 469740169, NULL, NULL, NULL, FALSE, '$2b$12$s/R/9wfJaCnpG5dBe1mvGeqjP0MKzUrUOZYZDuSfVwNb34MuW93O6', TRUE, '2024-09-07 12:13:41.994466+00', NULL),
                    (5, 904491755, NULL, NULL, NULL, FALSE, '$2b$12$N37Tx684nhyoaVGXFB3nQeMiJqCJ53A4qBhQL8KmfKcydQIitH3xq', TRUE, '2024-09-07 15:05:18.907019+00', NULL)
                    ON CONFLICT (telegram_id) DO NOTHING
                """)

                cur.execute("""
                    INSERT INTO reference_activities (user_id, activity_name, activity_type)
                    VALUES 
                    (1, 'Jumping', 'time'),
                    (1, 'Abs', 'reps'),
                    (2, 'Plank', 'time'),
                    (2, 'Side Plank', 'time'),
                    (2, 'Push Ups', 'reps'),
                    (3, 'Plank', 'time'),
                    (3, 'Push Ups', 'reps'),
                    (3, 'Abs', 'reps'),
                    (4, 'Plank', 'time'),
                    (4, 'Pull Ups', 'reps'),
                    (4, 'Squats', 'reps'),
                    (5, 'Plank', 'time'),
                    (5, 'Side Plank', 'time')
                    ON CONFLICT (user_id, activity_name) DO NOTHING
                """)	
     
                cur.execute("""
                    INSERT INTO activities (user_id, reference_activity_id, value, created_at)
                    VALUES 
                    (2, (SELECT id FROM reference_activities WHERE user_id = 2 AND activity_name = 'Plank'), 60, '2024-09-04'),
                    (2, (SELECT id FROM reference_activities WHERE user_id = 2 AND activity_name = 'Plank'), 70, '2024-09-05'),
                    (2, (SELECT id FROM reference_activities WHERE user_id = 2 AND activity_name = 'Plank'), 80, '2024-09-06'),
                    (2, (SELECT id FROM reference_activities WHERE user_id = 2 AND activity_name = 'Plank'), 80, '2024-09-07'),
                    (2, (SELECT id FROM reference_activities WHERE user_id = 2 AND activity_name = 'Plank'), 90, '2024-09-08'),
                    (2, (SELECT id FROM reference_activities WHERE user_id = 2 AND activity_name = 'Plank'), 90, '2024-09-09'),
                    (2, (SELECT id FROM reference_activities WHERE user_id = 2 AND activity_name = 'Side Plank'), 30, '2024-09-04'),
                    (2, (SELECT id FROM reference_activities WHERE user_id = 2 AND activity_name = 'Side Plank'), 40, '2024-09-05'),
                    (2, (SELECT id FROM reference_activities WHERE user_id = 2 AND activity_name = 'Side Plank'), 40, '2024-09-06'),
                    (2, (SELECT id FROM reference_activities WHERE user_id = 2 AND activity_name = 'Side Plank'), 40, '2024-09-07'),
                    (2, (SELECT id FROM reference_activities WHERE user_id = 2 AND activity_name = 'Side Plank'), 40, '2024-09-08'),
                    (2, (SELECT id FROM reference_activities WHERE user_id = 2 AND activity_name = 'Side Plank'), 40, '2024-09-09'),
                    (2, (SELECT id FROM reference_activities WHERE user_id = 2 AND activity_name = 'Push Ups'), 35, '2024-09-04'),
                    (2, (SELECT id FROM reference_activities WHERE user_id = 2 AND activity_name = 'Push Ups'), 40, '2024-09-05'),
                    (2, (SELECT id FROM reference_activities WHERE user_id = 2 AND activity_name = 'Push Ups'), 40, '2024-09-06'),
                    (2, (SELECT id FROM reference_activities WHERE user_id = 2 AND activity_name = 'Push Ups'), 40, '2024-09-07'),
                    (2, (SELECT id FROM reference_activities WHERE user_id = 2 AND activity_name = 'Push Ups'), 40, '2024-09-08'),
                    (5, (SELECT id FROM reference_activities WHERE user_id = 5 AND activity_name = 'Plank'), 30, '2024-09-04'),
                    (5, (SELECT id FROM reference_activities WHERE user_id = 5 AND activity_name = 'Plank'), 60, '2024-09-05'),
                    (5, (SELECT id FROM reference_activities WHERE user_id = 5 AND activity_name = 'Plank'), 75, '2024-09-06'),
                    (5, (SELECT id FROM reference_activities WHERE user_id = 5 AND activity_name = 'Plank'), 60, '2024-09-07'),
                    (5, (SELECT id FROM reference_activities WHERE user_id = 5 AND activity_name = 'Plank'), 60, '2024-09-08'),
                    (5, (SELECT id FROM reference_activities WHERE user_id = 5 AND activity_name = 'Plank'), 63, '2024-09-09'),
                    (5, (SELECT id FROM reference_activities WHERE user_id = 5 AND activity_name = 'Side Plank'), 10, '2024-09-04'),
                    (5, (SELECT id FROM reference_activities WHERE user_id = 5 AND activity_name = 'Side Plank'), 30, '2024-09-05'),
                    (5, (SELECT id FROM reference_activities WHERE user_id = 5 AND activity_name = 'Side Plank'), 20, '2024-09-06'),
                    (5, (SELECT id FROM reference_activities WHERE user_id = 5 AND activity_name = 'Side Plank'), 25, '2024-09-07'),
                    (5, (SELECT id FROM reference_activities WHERE user_id = 5 AND activity_name = 'Side Plank'), 30, '2024-09-08'),
                    (5, (SELECT id FROM reference_activities WHERE user_id = 5 AND activity_name = 'Side Plank'), 36, '2024-09-09'),
                    (4, (SELECT id FROM reference_activities WHERE user_id = 4 AND activity_name = 'Plank'), 20, '2024-09-04'),
                    (4, (SELECT id FROM reference_activities WHERE user_id = 4 AND activity_name = 'Plank'), 60, '2024-09-05'),
                    (4, (SELECT id FROM reference_activities WHERE user_id = 4 AND activity_name = 'Plank'), 60, '2024-09-06'),
                    (4, (SELECT id FROM reference_activities WHERE user_id = 4 AND activity_name = 'Plank'), 60, '2024-09-07'),
                    (4, (SELECT id FROM reference_activities WHERE user_id = 4 AND activity_name = 'Plank'), 60, '2024-09-08'),
                    (4, (SELECT id FROM reference_activities WHERE user_id = 4 AND activity_name = 'Pull Ups'), 7, '2024-09-04'),
                    (4, (SELECT id FROM reference_activities WHERE user_id = 4 AND activity_name = 'Pull Ups'), 7, '2024-09-05'),
                    (4, (SELECT id FROM reference_activities WHERE user_id = 4 AND activity_name = 'Pull Ups'), 7, '2024-09-06'),
                    (4, (SELECT id FROM reference_activities WHERE user_id = 4 AND activity_name = 'Pull Ups'), 7, '2024-09-07'),
                    (4, (SELECT id FROM reference_activities WHERE user_id = 4 AND activity_name = 'Pull Ups'), 10, '2024-09-08'),
                    (4, (SELECT id FROM reference_activities WHERE user_id = 4 AND activity_name = 'Squats'), 25, '2024-09-04'),
                    (4, (SELECT id FROM reference_activities WHERE user_id = 4 AND activity_name = 'Squats'), 30, '2024-09-05'),
                    (4, (SELECT id FROM reference_activities WHERE user_id = 4 AND activity_name = 'Squats'), 30, '2024-09-06'),
                    (4, (SELECT id FROM reference_activities WHERE user_id = 4 AND activity_name = 'Squats'), 25, '2024-09-07'),
                    (4, (SELECT id FROM reference_activities WHERE user_id = 4 AND activity_name = 'Squats'), 30, '2024-09-08'),
                    (3, (SELECT id FROM reference_activities WHERE user_id = 3 AND activity_name = 'Plank'), 20, '2024-09-04'),
                    (3, (SELECT id FROM reference_activities WHERE user_id = 3 AND activity_name = 'Plank'), 60, '2024-09-05'),
                    (3, (SELECT id FROM reference_activities WHERE user_id = 3 AND activity_name = 'Plank'), 93, '2024-09-06'),
                    (3, (SELECT id FROM reference_activities WHERE user_id = 3 AND activity_name = 'Plank'), 120, '2024-09-07'),
                    (3, (SELECT id FROM reference_activities WHERE user_id = 3 AND activity_name = 'Push Ups'), 15, '2024-09-04'),
                    (3, (SELECT id FROM reference_activities WHERE user_id = 3 AND activity_name = 'Push Ups'), 15, '2024-09-05'),
                    (3, (SELECT id FROM reference_activities WHERE user_id = 3 AND activity_name = 'Push Ups'), 13, '2024-09-06'),
                    (3, (SELECT id FROM reference_activities WHERE user_id = 3 AND activity_name = 'Push Ups'), 12, '2024-09-07'),
                    (3, (SELECT id FROM reference_activities WHERE user_id = 3 AND activity_name = 'Abs'), 20, '2024-09-04'),
                    (3, (SELECT id FROM reference_activities WHERE user_id = 3 AND activity_name = 'Abs'), 20, '2024-09-05'),
                    (3, (SELECT id FROM reference_activities WHERE user_id = 3 AND activity_name = 'Abs'), 63, '2024-09-06'),
                    (3, (SELECT id FROM reference_activities WHERE user_id = 3 AND activity_name = 'Abs'), 40, '2024-09-07')
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