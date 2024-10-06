from psycopg2 import pool
from config import *
from logger import log_error


class Database:
    def __init__(self):
        self.connection_pool = pool.SimpleConnectionPool(
            1, 20,
            host=POSTGRES_HOST,
            dbname=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            port=5432
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

    def get_user_by_id(self, user_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
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

    def get_reference_activities(self, user_id, limit=None):
        query = """
        SELECT id, activity_name, activity_type 
        FROM reference_activities 
        WHERE user_id = %s 
        ORDER BY id ASC
        """
        if limit:
            query += " LIMIT %s"
            params = (user_id, limit)
        else:
            params = (user_id,)
        
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
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

    def update_activity(self, activity_id, user_id, value=None, created_at=None):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                # Prepare the update query
                update_query = "UPDATE activities SET "
                update_params = []
                
                if value is not None:
                    update_query += "value = %s, "
                    update_params.append(value)
                
                if created_at is not None:
                    update_query += "created_at = %s, "
                    update_params.append(created_at)
                
                # Remove the trailing comma and space
                update_query = update_query.rstrip(", ")
                
                # Add the WHERE clause
                update_query += " WHERE id = %s AND user_id = %s"
                update_params.extend([activity_id, user_id])
                
                # Execute the query only if there are parameters to update
                if update_params:
                    cur.execute(update_query, update_params)
                    conn.commit()
                    return cur.rowcount > 0
                else:
                    return False  # No updates were made
        except Exception as e:
            log_error(f"Database error in update_activity: {str(e)}")
            return False
        finally:
            self.release_connection(conn)

    def delete_activity(self, activity_id: int, user_id: int) -> bool:
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM activities
                    WHERE id = %s AND user_id = %s
                """, (activity_id, user_id))
                deleted = cur.rowcount > 0
                conn.commit()
                return deleted
        except Exception as e:
            log_error(f"Error deleting activity: {str(e)}")
            return False
        finally:
            self.release_connection(conn)

    def get_recent_activities(self, user_id, limit=10):
        query = """
        SELECT a.id, ra.activity_name, a.value, ra.activity_type, a.created_at
        FROM activities a
        JOIN reference_activities ra ON a.reference_activity_id = ra.id
        WHERE a.user_id = %s
        ORDER BY a.created_at DESC
        LIMIT %s
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query, (user_id, limit))
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

    def get_activities_count_last_24h(self, start_time, end_time):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                query = """
                SELECT COUNT(*) 
                FROM activities 
                WHERE created_at BETWEEN %s AND %s
                """
                cur.execute(query, (start_time, end_time))
                return cur.fetchone()[0]
        finally:
            self.release_connection(conn)

    def get_total_users_count(self):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM users")
                return cur.fetchone()[0]
        finally:
            self.release_connection(conn)

    def was_user_active_today(self, user_id, date):
        query = """
        SELECT COUNT(*) FROM activities 
        JOIN users ON users.id = activities.user_id
        WHERE users.id = %s AND DATE(activities.created_at) = %s
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query, (user_id, date))
                count = cur.fetchone()[0]
                return count > 0
        finally:
            self.release_connection(conn)

    def get_activity_streaks(self, user_id):
        query = """
        WITH daily_activity AS (
            SELECT user_id, reference_activity_id, DATE(created_at) as activity_date
            FROM activities
            WHERE user_id = %s
            GROUP BY user_id, reference_activity_id, DATE(created_at)
        ),
        activity_counts AS (
            SELECT user_id, reference_activity_id, COUNT(DISTINCT activity_date) as days_active
            FROM daily_activity
            GROUP BY user_id, reference_activity_id
        )
        SELECT u.id, u.telegram_id, u.username, ra.activity_name, COALESCE(ac.days_active, 0) as days_active
        FROM users u
        JOIN reference_activities ra ON ra.user_id = u.id
        LEFT JOIN activity_counts ac ON u.id = ac.user_id AND ra.id = ac.reference_activity_id
        WHERE u.id = %s
        ORDER BY ra.activity_name;
        """
        return self.execute_query(query, (user_id, user_id))

    def update_activity_datetime(self, activity_id, user_id, new_datetime):
        try:
            with self.conn:
                self.conn.execute("""
                    UPDATE activities
                    SET created_at = ?
                    WHERE id = ? AND user_id = ?
                """, (new_datetime, activity_id, user_id))
            return True
        except Exception as e:
            log_error(f"Error updating activity datetime: {str(e)}")
            return False

    def get_activity_type(self, activity_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT ra.activity_type
                    FROM activities a
                    JOIN reference_activities ra ON a.reference_activity_id = ra.id
                    WHERE a.id = %s
                """, (activity_id,))
                return cur.fetchone()[0]
        finally:
            self.release_connection(conn)

    def get_reference_activities_without_activities(self, user_id):
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT r.id, r.activity_name, r.activity_type
                    FROM reference_activities r
                    LEFT JOIN activities a ON r.id = a.reference_activity_id
                    WHERE r.user_id = %s
                    GROUP BY r.id
                    HAVING COUNT(a.id) = 0
                    ORDER BY r.id ASC
                """, (user_id,))
                return cur.fetchall()
        finally:
            self.release_connection(conn)

    # Add this new method to the Database class

    def get_global_ranking(self):
        query = """
        SELECT 
            COALESCE(u.first_name, 'N/A') AS name,
            COUNT(DISTINCT ra.id) AS total_activities,
            COALESCE(SUM(CASE WHEN ra.activity_type = 'time' THEN a.value ELSE 0 END), 0) AS total_time,
            COALESCE(SUM(CASE WHEN ra.activity_type = 'reps' THEN a.value ELSE 0 END), 0) AS total_reps,
            COUNT(DISTINCT DATE(a.created_at)) AS days_active,
            MAX(a.created_at) AS last_active
        FROM 
            users u
        INNER JOIN 
            activities a ON u.id = a.user_id
        INNER JOIN 
            reference_activities ra ON a.reference_activity_id = ra.id
        WHERE 
            u.is_admin = FALSE
        GROUP BY 
            u.id, u.first_name
        HAVING
            COUNT(DISTINCT a.id) >= 1
        ORDER BY 
            days_active DESC, last_active DESC, total_time DESC, total_reps DESC
        LIMIT 10
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query)
                return cur.fetchall()
        finally:
            self.release_connection(conn)

db = Database()