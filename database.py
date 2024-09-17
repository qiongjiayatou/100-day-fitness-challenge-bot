import psycopg2
from psycopg2 import pool
import os
from dotenv import load_dotenv
from config import *


load_dotenv()

class Database:
    def __init__(self):
        self.connection_pool = psycopg2.pool.SimpleConnectionPool(
            1, 20,
            host=POSTGRES_HOST,
            dbname=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD
        )
        self.init_db()

    def get_connection(self):
        return self.connection_pool.getconn()

    def release_connection(self, conn):
        self.connection_pool.putconn(conn)

    def init_db(self):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        telegram_id BIGINT UNIQUE NOT NULL,
                        username VARCHAR(255),
                        first_name VARCHAR(255),
                        last_name VARCHAR(255),
                        is_admin BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS reference_activities (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER REFERENCES users(id),
                        activity_name VARCHAR(255) NOT NULL,
                        activity_type VARCHAR(50) NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS activities (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER REFERENCES users(id),
                        reference_activity_id INTEGER REFERENCES reference_activities(id),
                        value INTEGER NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
        finally:
            self.release_connection(conn)

    def add_user(self, telegram_id, username, first_name, last_name):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users (telegram_id, username, first_name, last_name)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (telegram_id) DO UPDATE
                    SET username = EXCLUDED.username,
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name
                    RETURNING id
                """, (telegram_id, username, first_name, last_name))
                user_id = cur.fetchone()[0]
                conn.commit()
                return user_id
        finally:
            self.release_connection(conn)

    def get_user(self, telegram_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
                return cur.fetchone()
        finally:
            self.release_connection(conn)

    def add_reference_activity(self, user_id, activity_name, activity_type):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO reference_activities (user_id, activity_name, activity_type)
                    VALUES (%s, %s, %s)
                    RETURNING id
                """, (user_id, activity_name, activity_type))
                activity_id = cur.fetchone()[0]
                conn.commit()
                return activity_id
        finally:
            self.release_connection(conn)

    def get_reference_activities(self, user_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, activity_name, activity_type FROM reference_activities WHERE user_id = %s", (user_id,))
                return cur.fetchall()
        finally:
            self.release_connection(conn)

    def add_activity(self, user_id, reference_activity_id, value):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO activities (user_id, reference_activity_id, value)
                    VALUES (%s, %s, %s)
                    RETURNING id
                """, (user_id, reference_activity_id, value))
                activity_id = cur.fetchone()[0]
                conn.commit()
                return activity_id
        finally:
            self.release_connection(conn)

    def get_activities(self, user_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT a.id, r.activity_name, a.value, r.activity_type, a.created_at
                    FROM activities a
                    JOIN reference_activities r ON a.reference_activity_id = r.id
                    WHERE a.user_id = %s
                    ORDER BY a.created_at DESC
                """, (user_id,))
                return cur.fetchall()
        finally:
            self.release_connection(conn)

    def get_activity(self, activity_id, user_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, value, reference_activity_id FROM activities WHERE id = %s AND user_id = %s", (activity_id, user_id))
                return cur.fetchone()
        finally:
            self.release_connection(conn)

    def update_activity(self, activity_id, user_id, new_value):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE activities SET value = %s WHERE id = %s AND user_id = %s", (new_value, activity_id, user_id))
                conn.commit()
                return True
        finally:
            self.release_connection(conn)

    def delete_activity(self, activity_id, user_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM activities WHERE id = %s AND user_id = %s", (activity_id, user_id))
                conn.commit()
                return True
        finally:
            self.release_connection(conn)

    def get_recent_activities(self, user_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT a.id, r.activity_name, a.value, r.activity_type, a.created_at
                    FROM activities a
                    JOIN reference_activities r ON a.reference_activity_id = r.id
                    WHERE a.user_id = %s
                    ORDER BY a.created_at DESC
                """, (user_id,))
                return cur.fetchall()
        finally:
            self.release_connection(conn)

    def get_total_activities_count(self, user_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM activities WHERE user_id = %s", (user_id,))
                return cur.fetchone()[0]
        finally:
            self.release_connection(conn)

    def get_unique_activities_count(self, user_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(DISTINCT reference_activity_id) FROM activities WHERE user_id = %s", (user_id,))
                return cur.fetchone()[0]
        finally:
            self.release_connection(conn)

    def get_most_frequent_activity(self, user_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT r.activity_name, COUNT(*) as count
                    FROM activities a
                    JOIN reference_activities r ON a.reference_activity_id = r.id
                    WHERE a.user_id = %s
                    GROUP BY r.activity_name
                    ORDER BY count DESC
                """, (user_id,))
                return cur.fetchone()
        finally:
            self.release_connection(conn)

    def get_all_activities(self, user_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT a.id, r.activity_name, a.value, r.activity_type, a.created_at
                    FROM activities a
                    JOIN reference_activities r ON a.reference_activity_id = r.id
                    WHERE a.user_id = %s
                    ORDER BY a.created_at DESC
                """, (user_id,))
                return cur.fetchall()
        finally:
            self.release_connection(conn)

    def get_last_activity(self, activity_name):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT a.id, a.value, a.created_at
                    FROM activities a
                    JOIN reference_activities r ON a.reference_activity_id = r.id
                    WHERE r.activity_name = %s
                    ORDER BY a.created_at DESC
                """, (activity_name,))
                return cur.fetchone()
        finally:
            self.release_connection(conn)

    def get_activities_count_for_today(self, user_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM activities a
                    JOIN reference_activities r ON a.reference_activity_id = r.id
                    WHERE a.user_id = %s AND a.created_at >= CURRENT_DATE
                """, (user_id,))
                return cur.fetchone()[0]
        finally:
            self.release_connection(conn)

    def update_user(self, telegram_id, username, first_name, last_name):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE users 
                    SET username = %s, first_name = %s, last_name = %s 
                    WHERE telegram_id = %s
                    RETURNING id
                """, (username, first_name, last_name, telegram_id))
                user_id = cur.fetchone()[0]
                conn.commit()
                return user_id
        finally:
            self.release_connection(conn)

    def execute_query(self, query, params=None):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchall()
        finally:
            self.release_connection(conn)

    def get_reference_activity(self, activity_id, user_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT activity_name, activity_type
                    FROM reference_activities
                    WHERE id = %s AND user_id = %s
                """, (activity_id, user_id))
                return cur.fetchone()
        finally:
            self.release_connection(conn)

    def update_reference_activity(self, activity_id, user_id, new_name, new_type):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE reference_activities
                    SET activity_name = %s, activity_type = %s
                    WHERE id = %s AND user_id = %s
                    RETURNING id
                """, (new_name, new_type, activity_id, user_id))
                updated_id = cur.fetchone()
                conn.commit()
                return updated_id is not None
        finally:
            self.release_connection(conn)

    def delete_reference_activity(self, activity_id, user_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                # First, delete all activities associated with this reference activity
                cur.execute("""
                    DELETE FROM activities
                    WHERE reference_activity_id = %s AND user_id = %s
                """, (activity_id, user_id))
                
                # Then, delete the reference activity itself
                cur.execute("""
                    DELETE FROM reference_activities
                    WHERE id = %s AND user_id = %s
                    RETURNING id
                """, (activity_id, user_id))
                deleted_id = cur.fetchone()
                conn.commit()
                return deleted_id is not None
        finally:
            self.release_connection(conn)

    def get_activity_count_for_reference(self, reference_activity_id, user_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*)
                    FROM activities
                    WHERE reference_activity_id = %s AND user_id = %s
                """, (reference_activity_id, user_id))
                return cur.fetchone()[0]
        finally:
            self.release_connection(conn)

    def get_all_users(self):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, telegram_id, username, first_name, last_name, is_admin FROM users")
                return cur.fetchall()
        finally:
            self.release_connection(conn)

db = Database()

