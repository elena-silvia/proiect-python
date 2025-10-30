import sqlite3
import os

CALE_DB = os.path.join(os.path.dirname(__file__), "music.db")
#calea catre baza de date, creaaza drumul catre baza de date music.db (cu comanda os.path.join) in acelasi
# loc in care se afla si acest fisier(__file__=baza_de_date)
#numele variabilelor care nu se schimba se scrie cu litere mari (conventie)

conn = sqlite3.connect(CALE_DB) #conn= connection, conexiune dintre python si sql
c=conn.cursor() #c e variabila prin intermediul careia modific baza de date

c.execute("CREATE TABLE IF NOT EXISTS melodii (id INTEGER PRIMARY KEY AUTOINCREMENT, nume TEXT, cale TEXT)")
#tabel cu coloanele id, nume, cale
# id e primary key, creste cu fiecare rand
# nume si cale sunt string-uri, id e int

FILES_PATH = os.path.join(os.path.dirname(__file__), "fisiere")

c.execute("DELETE FROM melodii")
conn.commit()
#sterg tot ce era inainte in baza de date, altfel la fiecare run ar adauga din nou aaceleasi melodii si as irosi spatiul cu copii

c.execute("DELETE FROM sqlite_sequence WHERE name='melodii'")
#Resetez si contorul intern din autoincrement (ca id sa plece iar de la 1), altfel am aceleasi melodii dar la fiecare run creste nr din id

for a in os.listdir(FILES_PATH):
    if a.endswith(".mp3"):
        b = os.path.join(FILES_PATH, a)
        c.execute("INSERT INTO melodii (nume, cale) VALUES (?, ?)", (a,b))

conn.commit() #salveaza schimbarile din baza de date

# afișăm toate melodiile
c.execute("SELECT id, nume FROM melodii") #iau toate valorile de id si de nume
melodii = c.fetchall() # le pun in melodii, care e ca un fel de matrice
for m in melodii: # m se duce pe fiecare linie si afiseaza coloane 0 (id) si coloana 1(nume)
    print(m[0], m[1])

#conn.close()

