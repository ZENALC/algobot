# Simple function that creates the initial table jobs with its respective columns.
def create_table(connection: sqlite3.Connection, cursor: sqlite3.Cursor):
    cursor.execute('''CREATE TABLE IF NOT EXISTS jobs(
                       id TEXT PRIMARY KEY,
                       Position_Type TEXT,
                       URL TEXT NOT NULL,
                       Created_at TEXT NOT NULL,
                       Company TEXT NOT NULL,
                       Company_URL TEXT,
                       Location TEXT,
                       Title TEXT NOT NULL,
                       Description TEXT NOT NULL,
                       How_To_Apply TEXT,
                       Company_Logo TEXT,
                       geo_latitude TEXT,
                       geo_longitude TEXT
                        );''')
    commit_db(connection)