import sqlite3

DB_NAME="users.db"

def setup_user_db():
    conn=sqlite3.connect(DB_NAME)
    c=conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY, password TEXT NOT NULL)""")
    c.execute("INSERT OR IGNORE INTO users VALUES (?,?)",('elena','parola'))
    c.execute("INSERT OR IGNORE INTO users VALUES (?,?)", ('coleg','parola456'))

    conn.commit() #salveaza schimbarile in users.db
    conn.close()
    print(f"Baza de date {DB_NAME} a fost creata si populata")

if __name__ == "__main__":
    setup_user_db()
