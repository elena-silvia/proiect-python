import sqlite3
import os

CALE_DB = os.path.join(os.path.dirname(__file__), "music.db")


def initializeaza_db_muzica():
    conn = sqlite3.connect(CALE_DB)
    c = conn.cursor()

    # NOU: Am adaugat coloana 'username'
    c.execute("""CREATE TABLE IF NOT EXISTS melodii
                 (
                     id
                     INTEGER
                     PRIMARY
                     KEY
                     AUTOINCREMENT,
                     nume
                     TEXT,
                     cale
                     TEXT,
                     username
                     TEXT
                 )""")

    conn.commit()
    conn.close()
    print("Baza de date muzicală verificată/creată.")


if __name__ == "__main__":
    initializeaza_db_muzica()