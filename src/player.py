import pygame
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "music.db")

pygame.mixer.init()  # inițializează modul audio

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# afișăm toate melodiile
c.execute("SELECT id, nume, cale FROM melodii")
melodii = c.fetchall()
for m in melodii:
    print(m[0], m[1])

# alegerea melodiei de redat
id_alegere = int(input("Alege id-ul melodiei: "))

# căutăm melodia în baza de date
c.execute("SELECT nume, cale FROM melodii WHERE id = ?", (id_alegere,))
rezultat = c.fetchone()

if rezultat:
    nume, cale = rezultat
    print(f"Redare melodie: {nume}")
    pygame.mixer.music.load(cale)
    pygame.mixer.music.play()
    input("Apasă Enter pentru a opri redarea...")
    pygame.mixer.music.stop()
else:
    print("Melodia cu acest id nu există.")

conn.close()
