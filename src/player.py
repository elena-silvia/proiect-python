import pygame
import sqlite3
import os
import tkinter as tk  # importam tkinter pentru listbox
import customtkinter as ctk  # interfata moderna
from tkinter import Listbox, Button, END, messagebox, Frame, Label  # widget uri
from customtkinter import CTkFrame
from tkinter import filedialog
import shutil
from mutagen.mp3 import MP3
import random #pentru functia shuffle

# --- Variabile Globale ---
current_user = None
offset_timp = 0
lungime_melodie_curenta = 0
is_dragging = False
playlist_activ = False
cale_melodie_curenta = ""

shuffle_mode = False  # True: reda aleatoriu; False: reda secvential
song_queue = []  # Aici tinem minte indexurile melodiilor puse in coada
is_paused = False  # Variabila noua pentru starea de pauza

# Aceasta lista va tine minte datele reale pentru a rezolva problema indexului
playlist_data = []

# construim o cale absoluta catre fisierul bazei de date
DB_PATH = os.path.join(os.path.dirname(__file__), "music.db")

# Initializare standard Pygame Mixer
pygame.mixer.init(frequency=44100)
# Definim un eveniment personalizat (ramane, desi nu mai e folosit direct, e mai sigur)
MUSIC_END_EVENT = pygame.USEREVENT + 1
# Spunem player-ului sa declanseze acest eveniment cand se termina melodia
pygame.mixer.music.set_endevent(MUSIC_END_EVENT)


def format_timp(secunde):
    #  Rotunjim secundele (Round) in loc sa le taiem (Int) ---
    # Astfel 3:59.9 devine 4:00, exact ca pe YouTube
    secunde_rotunjite = round(secunde)

    minute = int(secunde_rotunjite // 60)
    sec = int(secunde_rotunjite % 60)
    return f"{minute:02d}:{sec:02d}"


def autentificare(username, password):
    # verifica datele de logare in baza de date user.db
    DB_NAME = "users.db"
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        # cauta o potrivire cu cele "hardcodate"
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user_record = c.fetchone()  # preluam utilizatorul
        conn.close()
        if user_record:
            return True  # autentificare reusita
        else:
            return False  # autentificare gresita
    except sqlite3.Error as e:
        # returneaza erori sql
        print(f"Eroare SQLite la autentificare:{e}")
        return False


def inregistrare_user(username, password):
    DB_NAME = "users.db"
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=?", (username,))
        if c.fetchone():
            conn.close()
            return False, "Utilizatorul exista deja!"

        c.execute("INSERT INTO users VALUES (?, ?)", (username, password))
        conn.commit()
        conn.close()
        return True, "Cont creat cu succes!"
    except sqlite3.Error as e:
        return False, f"Eroare baza de date: {e}"


def login(event=None):
    global current_user
    # fuctie pentru logare(cand se apasa butonul login)
    username = username_entry.get()  # username_entry este o variabila globala
    # ce poate fi schimbata si este declarata in create_mainloop
    password = password_entry.get()
    if autentificare(username, password):
        current_user = username
        login_window.destroy()  # daca se reuseste logarea, se inchide fereastra de login

        root.deiconify()  # inchide pagina de logare si afiseaza player-ul
        root.title(f"MP3 Player - Logat ca: {current_user}")
        incarcare_melodii()
    else:
        messagebox.showerror("Eroare", "Nume utilizator sau parola incorecte!")
        password_entry.delete(0, 'end')  # se goleste campul de melodii


def get_melodii(filtru_nume=""):
    # extragem melodii din baza de date
    conn = sqlite3.connect(DB_PATH)  # aici stabilim conexiunea cu baza de date
    c = conn.cursor()  # creeaza un cursor pentru a executa comenzi sql

    # alegem id-ul,numele si calea fiecarei melodii din tabelul 'melodii'
    if filtru_nume:
        c.execute("SELECT id, nume, cale FROM melodii WHERE username=? AND nume LIKE ?",
                  (current_user, f"%{filtru_nume}%"))
    else:
        c.execute("SELECT id, nume, cale FROM melodii WHERE username=?", (current_user,))

    melodii = c.fetchall()  # preluam toate datele intr-o lista de tupluri
    conn.close()  # inchidem conexiunea
    return melodii  # returnam lista cu melodii


def verificare_sfarsit_melodie():
    global playlist_activ

    # Daca player-ul canta, revenim peste 100ms sa verificam iar
    if pygame.mixer.music.get_busy():
        root.after(100, verificare_sfarsit_melodie)
        return

    # Daca s-a oprit (get_busy e False)
    # Verificam SA NU FIE PE PAUZA si playlist-ul sa fie activ
    if playlist_activ and not is_paused:
        next_melodie()


def update_progres():
    global is_dragging, lungime_melodie_curenta

    # Actualizam doar daca canta si nu tragi tu de slider
    if pygame.mixer.music.get_busy() and not is_dragging:

        timp_curent_intern = pygame.mixer.music.get_pos() / 1000
        timp_total_real = timp_curent_intern + offset_timp

        # Actualizam Slider-ul
        if lungime_melodie_curenta > 0:
            valoare_slider = timp_total_real / lungime_melodie_curenta
            if valoare_slider > 1: valoare_slider = 1
            slider_progres.set(valoare_slider)

        # afisam timpul curent
        timp_curent_str = format_timp(timp_total_real)
        time_label.configure(text=f"{timp_curent_str}")

    # Continuam bucla (verificam sa nu fie pauza)
    if playlist_activ and not is_paused:
        root.after(500, update_progres)


def seek_melodie(valoare):
    global offset_timp
    if lungime_melodie_curenta > 0:
        timp_target = float(valoare) * lungime_melodie_curenta

        pygame.mixer.music.set_pos(timp_target)

        offset_timp = timp_target

        # Afisam doar timpul nou selectat
        timp_curent_str = format_timp(timp_target)
        time_label.configure(text=f"{timp_curent_str}")


def set_volum(valoare):
    volum = float(valoare)
    pygame.mixer.music.set_volume(volum)


def start_drag(event):
    global is_dragging
    is_dragging = True


def stop_drag(event):
    global is_dragging
    is_dragging = False
    valoare = slider_progres.get()
    seek_melodie(valoare)


def obtine_durata_reala(cale_fisier):
    try:
        audio = MP3(cale_fisier)
        return audio.info.length
    except:
        return 0  # Sau fallback la pygame, dar Mutagen e baza


def play_melodie(event=None):
    global playlist_activ, lungime_melodie_curenta, offset_timp, cale_melodie_curenta, is_paused
    is_paused = False
    try:
        # Verificare selectie
        try:
            select_index = lista_melodii.curselection()[0]
        except IndexError:
            # Daca userul da dublu click fara selectie valida
            return

        melodie_data = playlist_data[select_index]
        nume_melodie = melodie_data[1]
        cale_melodie = melodie_data[2]

        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()

        # --- TENTATIVA FIX FRECVENTA ---
        try:
            audio_info = MP3(cale_melodie).info
            frecventa_reala = audio_info.sample_rate
            lungime_melodie_curenta = audio_info.length

            # Printam pentru debug (sa vedem in consola daca merge)
            # print(f"Frecventa detectata: {frecventa_reala} Hz | Durata: {lungime_melodie_curenta} sec")

            # Resetam mixerul
            if pygame.mixer.get_init():
                pygame.mixer.quit()
            pygame.mixer.init(frequency=frecventa_reala)

        except Exception as e:
            # print(f"NU s-a putut seta frecventa (folosim standard): {e}")
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            # Fallback durata
            lungime_melodie_curenta = obtine_durata_reala(cale_melodie)
        # -------------------------------

        # Definim evenimentul de sfarsit (CRITIC pentru trecerea automata)
        try:
            MUSIC_END_EVENT = pygame.USEREVENT + 1
            pygame.mixer.music.set_endevent(MUSIC_END_EVENT)
        except:
            pass

        pygame.mixer.music.load(cale_melodie)
        pygame.mixer.music.play()

        cale_melodie_curenta = cale_melodie

        current_vol = slider_volum.get()
        pygame.mixer.music.set_volume(current_vol)

        offset_timp = 0
        playlist_activ = True
        status_label.configure(text=f"Redare muzica: {nume_melodie}")
        pauza_button.configure(text="Pauză", fg_color="#3B8ED0")  # Resetam culoarea butonului de pauza

        # Reset interfata - DOAR 00:00
        slider_progres.set(0)
        time_label.configure(text="00:00")  # Simplu, fara total

        update_progres()
        root.after(100, verificare_sfarsit_melodie)

    except Exception as e:
        messagebox.showerror("Eroare", f"Eroare neasteptata: {e}")


def stop_melodie(event=None):
    # Functie care opreste redarea melodiei (folosita intern de stergere)
    global playlist_activ, cale_melodie_curenta

    pygame.mixer.music.stop()
    playlist_activ = False
    cale_melodie_curenta = ""

    # Resetam interfata
    status_label.configure(text="Redare oprita")
    time_label.configure(text="00:00")  # Simplu, fara total
    slider_progres.set(0)


def pauza_melodie():
    global is_paused

    if not playlist_activ:
        return

    if not is_paused:
        # Punem Pauza
        pygame.mixer.music.pause()
        is_paused = True
        status_label.configure(text="Pauză")
        pauza_button.configure(text="Reia", fg_color="orange")  # Schimbam culoarea ca sa se vada
    else:
        # Scoatem Pauza (Unpause)
        pygame.mixer.music.unpause()
        is_paused = False
        status_label.configure(text=f"Redare: {os.path.basename(cale_melodie_curenta)}")
        pauza_button.configure(text="Pauză", fg_color="#3B8ED0")  # Revenim la culoarea albastra


def handle_space(event):
    # Daca nu canta nimic, incercam sa dam Play la selectie
    if not playlist_activ:
        try:
            if lista_melodii.curselection():
                play_melodie()
        except:
            pass
    else:
        # Altfel facem toggle Pauza/Reia
        pauza_melodie()


def handle_arrow(event):
    # Daca nu canta nimic, ignoram
    if not playlist_activ or lungime_melodie_curenta == 0:
        return

    # 1. Aflam timpul curent exact
    timp_curent = (pygame.mixer.music.get_pos() / 1000) + offset_timp

    # 2. Decidem directia (5 secunde inainte sau inapoi)
    step = 5
    if event.keysym == 'Right':
        timp_nou = timp_curent + step
    else:  # Left
        timp_nou = timp_curent - step

    # 3. Punem limite (sa nu mergem sub 0 sau peste durata)
    if timp_nou < 0: timp_nou = 0
    # Lasam o marja mica de 1 secunda la final
    if timp_nou >= lungime_melodie_curenta - 1: timp_nou = lungime_melodie_curenta - 1

    # 4. Convertim in valoare 0-1 pentru slider si seek
    valoare_noua = timp_nou / lungime_melodie_curenta

    # 5. Aplicam modificarea
    slider_progres.set(valoare_noua)
    seek_melodie(valoare_noua)


def set_selection(index):
    # Verificam limita listei(folosita de Next/Inapoi)
    total_melodii = lista_melodii.size()
    if total_melodii == 0:
        return  # Daca lista e goala nu se intampla nimic
    if index >= total_melodii:
        index = 0  # daca indexul depaseste limita revenim la prima melodie
    elif index < 0:
        index = total_melodii - 1  # daca indexul e in limita inferioara trece la ultima melodie
    lista_melodii.selection_clear(0, END)  # deselecteaza melodia dupa ce a fost selectata
    lista_melodii.activate(index)
    lista_melodii.select_set(index, last=None)  # evidentiaza melodia selectata

    play_melodie()


def next_melodie():
    global song_queue

    # 1. PRIORITATE ZERO: Coada de asteptare
    if len(song_queue) > 0:
        # Scoatem prima melodie din coada (FIFO - First In, First Out)
        next_index = song_queue.pop(0)

        # Actualizam statusul cozii in titlul ferestrei (optional, vizual)
        root.title(f"MP3 Player - Melodii in coada: {len(song_queue)}")

        set_selection(next_index)
        return

    # 2. PRIORITATE UNU: Shuffle
    if shuffle_mode:
        total_melodii = lista_melodii.size()
        if total_melodii > 1:
            # Alegem un numar random, dar incercam sa nu fie fix aceeasi melodie
            current_index = 0
            try:
                current_index = lista_melodii.curselection()[0]
            except:
                pass

            next_index = current_index
            while next_index == current_index:
                next_index = random.randint(0, total_melodii - 1)

            set_selection(next_index)
            return

    # 3. COMPORTAMENT NORMAL (Secvential)
    try:
        current_index = lista_melodii.curselection()[0]
    except IndexError:
        current_index = -1
    new_index = current_index + 1
    set_selection(new_index)


def melodie_anterioara():
    # calculeaza si seteaza indexul anterior pt Inapoi
    try:
        current_index = lista_melodii.curselection()[0]
    except IndexError:
        current_index = 0
    new_index = current_index - 1
    set_selection(new_index)


def adauga_melodie_noua():
    cale_fisier = filedialog.askopenfilename(filetypes=[("MP3 Files", "*.mp3")])
    if not cale_fisier:
        return

    nume_fisier = os.path.basename(cale_fisier)
    folder_destinatie = os.path.join(os.path.dirname(__file__), "fisiere")

    if not os.path.exists(folder_destinatie):
        os.makedirs(folder_destinatie)

    cale_noua = os.path.join(folder_destinatie, nume_fisier)

    if os.path.abspath(cale_fisier) != os.path.abspath(cale_noua):
        try:
            shutil.copy(cale_fisier, cale_noua)
        except Exception as e:
            messagebox.showerror("Eroare", f"Nu s-a putut copia fișierul: {e}")
            return
    else:
        pass

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO melodii (nume, cale, username) VALUES (?, ?, ?)",
                  (nume_fisier, cale_noua, current_user))
        conn.commit()
        conn.close()

        messagebox.showinfo("Succes", "Melodie adăugată în playlist-ul tău!")
        incarcare_melodii()
    except sqlite3.Error as e:
        messagebox.showerror("Eroare DB", str(e))


def sterge_melodie():
    try:
        select_index = lista_melodii.curselection()[0]

        melodie_data = playlist_data[select_index]
        id_melodie = melodie_data[0]
        cale_melodie_stearsa = melodie_data[2]

        if cale_melodie_stearsa == cale_melodie_curenta:
            stop_melodie()

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM melodii WHERE id=?", (id_melodie,))
        conn.commit()
        conn.close()

        incarcare_melodii()

    except IndexError:
        messagebox.showerror("Eroare", "Selectează o melodie pentru a o șterge!")
    except sqlite3.Error as e:
        messagebox.showerror("Eroare DB", str(e))


def incarcare_melodii(event=None):
    # incarca toate melodiile din baza de date in interfata Listbox
    global playlist_data

    text_cautat = search_entry.get()
    lista_melodii.delete(0, END)  # sterge ce era afisat anterior

    playlist_data = get_melodii(text_cautat)  # preluam alte melodii

    for index, (id_db, nume_melodie, cale_melodie) in enumerate(playlist_data):
        afisaj = f"{index + 1}. {nume_melodie}"
        lista_melodii.insert(END, afisaj)


def toggle_shuffle():
    global shuffle_mode
    shuffle_mode = not shuffle_mode  # Inversam starea (True/False)

    if shuffle_mode:
        shuffle_button.configure(fg_color="blue", text="Shuffle: ON")
    else:
        shuffle_button.configure(fg_color="gray", text="Shuffle: OFF")


def adauga_la_coada(event=None):
    # Aceasta functie se activeaza la Click Dreapta pe lista
    try:
        # Aflam pe ce element s-a dat click
        index_selectat = lista_melodii.nearest(event.y)

        # Il adaugam in lista noastra invizibila
        song_queue.append(index_selectat)

        # Feedback vizual pentru utilizator
        melodie_nume = playlist_data[index_selectat][1]
        status_label.configure(text=f"Adaugat in coada: {melodie_nume}")
        root.title(f"MP3 Player - Melodii in coada: {len(song_queue)}")

    except Exception as e:
        print(e)


def arata_meniu_contextual(event):
    # Cand dai click dreapta, apare meniul
    meniu_coada.tk_popup(event.x_root, event.y_root)


def deschide_manager_coada():
    # Cream o fereastra secundara (pop-up)
    coada_window = ctk.CTkToplevel(root)
    coada_window.title("Manager Coadă")
    coada_window.geometry("400x400")

    # Titlu
    ctk.CTkLabel(coada_window, text="Melodii ce urmează:", font=("Arial", 16, "bold")).pack(pady=10)

    # Lista vizuala pentru coada
    lista_coada_vizuala = Listbox(
        coada_window,
        width=50,
        height=15,
        font=('Arial', 10)
    )
    lista_coada_vizuala.pack(pady=5, padx=10)

    # Functie interna pentru a reimprospata lista
    def refresh_lista():
        lista_coada_vizuala.delete(0, END)
        if not song_queue:
            lista_coada_vizuala.insert(END, "(Coada este goală)")
        else:
            for i, index_melodie in enumerate(song_queue):
                # Luam numele melodiei din playlist_data
                try:
                    nume = playlist_data[index_melodie][1]
                    lista_coada_vizuala.insert(END, f"{i + 1}. {nume}")
                except:
                    lista_coada_vizuala.insert(END, "Eroare nume")

    # Functie pentru a sterge din coada
    def sterge_din_coada():
        try:
            # Vedem ce a selectat userul in aceasta fereastra
            selectie = lista_coada_vizuala.curselection()[0]

            # Stergem din lista reala (song_queue)
            # Nota: daca lista afiseaza "(Coada este goala)", ignoram
            if song_queue:
                del song_queue[selectie]
                refresh_lista()  # Actualizam vizual
                root.title(f"MP3 Player - Melodii in coada: {len(song_queue)}")
        except IndexError:
            pass

    # Buton stergere
    btn_sterge = ctk.CTkButton(
        coada_window,
        text="Șterge selecția",
        command=sterge_din_coada,
        fg_color="darkred"
    )
    btn_sterge.pack(pady=10)

    # Incarcam lista prima data
    refresh_lista()


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

root = ctk.CTk()  # Fereastra principala
root.title("MP3 Player")

# --- ACTIVARE TASTATURA ---
root.bind('<space>', handle_space)
root.bind('<Left>', handle_arrow)
root.bind('<Right>', handle_arrow)
# --------------------------

search_frame = ctk.CTkFrame(root)
search_frame.pack(fill=tk.X, padx=10, pady=(10, 0))

search_label = ctk.CTkLabel(search_frame, text="Caută:")
search_label.pack(side=tk.LEFT, padx=5)

search_entry = ctk.CTkEntry(search_frame, placeholder_text="Nume melodie...")
search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
search_entry.bind("<KeyRelease>", incarcare_melodii)

lista_melodii = Listbox(
    root,
    width=50,
    height=15,
    selectmode=tk.SINGLE,  # selecteaza un singur element
    font=('Arial', 12)
)
# ... codul tau cu lista_melodii ...

# Meniu Click Dreapta
meniu_coada = tk.Menu(root, tearoff=0)
meniu_coada.add_command(label="Adaugă la Coadă", command=lambda: adauga_la_coada_selectie())


# Trebuie sa facem o mica functie intermediara pentru butonul din meniu
def adauga_la_coada_selectie():
    try:
        selection = lista_melodii.curselection()[0]
        song_queue.append(selection)
        status_label.configure(text=f"Adaugat la coada (Pozitia {len(song_queue)})")
    except:
        pass


# Legam click-ul dreapta de lista (Button-3 este click dreapta)
lista_melodii.bind("<Button-3>", arata_meniu_contextual)
lista_melodii.pack(pady=10, padx=10)
lista_melodii.bind("<Double-Button-1>", play_melodie)  # play la dublu click
control_frame = CTkFrame(root)  # Frame este un container in care ne pozitionam butoanele si le grupam
control_frame.pack(pady=5)

# --- RÂNDUL 0: Bara de Progres și Timpul (Ne-am asigurat că sunt la început) ---
slider_progres = ctk.CTkSlider(
    control_frame,
    from_=0,
    to=1,
    width=350
)
slider_progres.set(0)
slider_progres.grid(row=0, column=0, columnspan=4, pady=(5, 15), padx=5)

slider_progres.bind("<Button-1>", start_drag)
slider_progres.bind("<ButtonRelease-1>", stop_drag)

time_label = ctk.CTkLabel(control_frame, text="00:00")
time_label.grid(row=0, column=4, padx=5, pady=(5, 15))

# ============================================================
# ZONA DE CONTROALE (Layout final)
# ============================================================

# --- RÂNDUL 1: Navigare și Redare ---
anterior = ctk.CTkButton(
    control_frame,
    text="⏮",
    command=melodie_anterioara,
    fg_color="green",
    width=50
)
anterior.grid(row=1, column=0, padx=5, pady=5)

play_button = ctk.CTkButton(
    control_frame,
    text="▶ Play",
    command=play_melodie,
    fg_color="green",
    width=80
)
play_button.grid(row=1, column=1, padx=5, pady=5)

# Butonul NOU de Pauza
pauza_button = ctk.CTkButton(
    control_frame,
    text="Pauză",
    command=pauza_melodie,
    fg_color="#3B8ED0",  # Un albastru standard
    width=80
)
pauza_button.grid(row=1, column=2, padx=5, pady=5)

next_button = ctk.CTkButton(
    control_frame,
    text="⏭",
    command=next_melodie,
    fg_color="green",
    width=50
)
next_button.grid(row=1, column=3, padx=5, pady=5)

# --- RÂNDUL 2: Volum (Stop a fost sters) ---
volum_label = ctk.CTkLabel(control_frame, text="Volum:")
volum_label.grid(row=2, column=1, padx=5, pady=5, sticky="e")  # Aliniat la dreapta celulei

slider_volum = ctk.CTkSlider(
    control_frame,
    from_=0,
    to=1,
    command=set_volum,
    width=150
)
slider_volum.set(0.5)
slider_volum.grid(row=2, column=2, columnspan=2, padx=5, pady=5, sticky="w")  # Aliniat la stanga celulei

# --- RÂNDUL 3: Gestionare Melodii ---
add_button = ctk.CTkButton(
    control_frame,
    text="+ Adaugă",
    command=adauga_melodie_noua,
    fg_color="orange",
    width=140
)
add_button.grid(row=3, column=0, columnspan=2, pady=10, padx=5)

delete_button = ctk.CTkButton(
    control_frame,
    text="- Șterge",
    command=sterge_melodie,
    fg_color="red",  # Rosu simplu
    width=140
)
delete_button.grid(row=3, column=2, columnspan=2, pady=10, padx=5)

# --- RÂNDUL 4: Funcții Extra (Shuffle & Coada) ---
shuffle_button = ctk.CTkButton(
    control_frame,
    text="Shuffle: OFF",
    command=toggle_shuffle,
    fg_color="gray",
    width=140
)
shuffle_button.grid(row=4, column=0, columnspan=2, pady=5, padx=5)

coada_button = ctk.CTkButton(
    control_frame,
    text="Vezi Coada ☰",
    command=deschide_manager_coada,
    fg_color="#555555",  # Un gri mai inchis
    width=140
)
coada_button.grid(row=4, column=2, columnspan=2, pady=5, padx=5)

# ============================================================
# STATUS LABEL (Sub butoane)
# ============================================================
status_label = ctk.CTkLabel(
    root,
    text="Asteapta selectia...",
    text_color="white",
    fg_color="gray",
    corner_radius=5,
    anchor=tk.W
)
status_label.pack(fill=tk.X, padx=10, pady=5)


def create_mainloop():
    # Mecanismul pt logare si lansarea aplicatiei
    global username_entry, password_entry, login_window

    login_window = ctk.CTkToplevel(root)
    login_window.title("Autentificare")
    login_window.geometry("300x350")

    login_window.bind('<Return>', login)

    ctk.CTkLabel(login_window, text="Nume utilizator:").pack(pady=(10, 0))
    username_entry = ctk.CTkEntry(login_window)
    username_entry.pack(pady=5, padx=20)

    ctk.CTkLabel(login_window, text="Parola:").pack(pady=(10, 0))
    password_entry = ctk.CTkEntry(login_window, show="*")
    password_entry.pack(pady=5, padx=20)

    login_button = ctk.CTkButton(login_window, text="Login", command=login)
    login_button.pack(pady=10, padx=20)

    def comanda_inregistrare():
        user = username_entry.get()
        parola = password_entry.get()
        if not user or not parola:
            messagebox.showwarning("Atentie", "Completeaza ambele campuri!")
            return

        succes, mesaj = inregistrare_user(user, parola)
        if succes:
            messagebox.showinfo("Succes", mesaj)
        else:
            messagebox.showerror("Eroare", mesaj)

    register_button = ctk.CTkButton(
        login_window,
        text="Creează Cont Nou",
        command=comanda_inregistrare,
        fg_color="blue"
    )
    register_button.pack(pady=5, padx=20)

    root.withdraw()
    root.mainloop()


incarcare_melodii()
if __name__ == "__main__":  # "butonul' de ON al programului
    create_mainloop()