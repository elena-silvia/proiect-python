import pygame
import sqlite3
import os
import tkinter as tk
import customtkinter as ctk
from tkinter import Listbox, END, messagebox, filedialog, Menu
from customtkinter import CTkFrame, CTkInputDialog
import shutil
from mutagen.mp3 import MP3
import random

# --- Variabile Globale ---
current_user = None
active_playlist_id = None  # None = Biblioteca principala, Int = ID Playlist
offset_timp = 0
lungime_melodie_curenta = 0
is_dragging = False
playlist_activ = False
cale_melodie_curenta = ""

shuffle_mode = False
loop_mode = 0
song_queue = []
is_paused = False

playlist_data = []  # Lista curenta de melodii afisata in UI

DB_PATH = os.path.join(os.path.dirname(__file__), "music.db")

pygame.mixer.init(frequency=44100)
MUSIC_END_EVENT = pygame.USEREVENT + 1
pygame.mixer.music.set_endevent(MUSIC_END_EVENT)

# --- CONFIGURARE DESIGN ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

THEME_COLORS = {
    "Spotify Green": "#1DB954",
    "Ocean Blue": "#3498db",
    "Royal Purple": "#9b59b6",
    "Sunset Orange": "#e67e22",
    "Hot Pink": "#e91e63",
    "Cyber Yellow": "#f1c40f"
}
COLOR_ACCENT = THEME_COLORS["Spotify Green"]
COLOR_BG_CARD = ("#ebebeb", "#2b2b2b")
COLOR_TEXT_LIST = ("black", "white")
COLOR_BG_LIST = ("#ffffff", "#1e1e1e")


# =========================================================
#                    CLASA TOOLTIP
# =========================================================
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        x, y, _cx, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 25
        y = y + cy + self.widget.winfo_rooty() + 25
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def hide_tip(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


# =========================================================
#                    FUNCTII UTILITARE
# =========================================================

def format_timp(secunde):
    secunde_rotunjite = round(secunde)
    minute = int(secunde_rotunjite // 60)
    sec = int(secunde_rotunjite % 60)
    return f"{minute:02d}:{sec:02d}"


def obtine_durata_reala(cale_fisier):
    try:
        audio = MP3(cale_fisier)
        return audio.info.length
    except:
        return 0


# =========================================================
#               BAZA DE DATE & LOGARE
# =========================================================

def init_db():
    """Creaza tabelele necesare daca nu exista"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Tabel Melodii (Master Library)
    c.execute('''CREATE TABLE IF NOT EXISTS melodii
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
                 )''')

    # Tabel Playlists (Nume playlisturi)
    c.execute('''CREATE TABLE IF NOT EXISTS playlists
                 (
                     id
                     INTEGER
                     PRIMARY
                     KEY
                     AUTOINCREMENT,
                     nume
                     TEXT,
                     username
                     TEXT
                 )''')

    # Tabel Legatura (Ce melodii sunt in ce playlist)
    c.execute('''CREATE TABLE IF NOT EXISTS playlist_songs
    (
        playlist_id
        INTEGER,
        song_id
        INTEGER,
        FOREIGN
        KEY
                 (
        playlist_id
                 ) REFERENCES playlists
                 (
                     id
                 ),
        FOREIGN KEY
                 (
                     song_id
                 ) REFERENCES melodii
                 (
                     id
                 ))''')

    conn.commit()
    conn.close()


def autentificare(username, password):
    DB_NAME = "users.db"
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS users (username text, password text)")
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user_record = c.fetchone()
        conn.close()
        return True if user_record else False
    except sqlite3.Error:
        return False


def inregistrare_user(username, password):
    DB_NAME = "users.db"
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS users (username text, password text)")
        c.execute("SELECT * FROM users WHERE username=?", (username,))
        if c.fetchone():
            conn.close()
            return False, "Utilizatorul exista deja!"
        c.execute("INSERT INTO users VALUES (?, ?)", (username, password))
        conn.commit()
        conn.close()
        return True, "Cont creat cu succes!"
    except sqlite3.Error as e:
        return False, f"Eroare DB: {e}"


def login(event=None):
    global current_user
    username = username_entry.get()
    password = password_entry.get()

    if autentificare(username, password):
        current_user = username
        login_window.destroy()
        root.deiconify()
        root.title(f"MP3 Player - {current_user}")

        # Initializeaza baza de date muzica
        init_db()

        # Incarca UI
        reimprospatare_sidebar_playlists()
        incarcare_melodii()  # Incarca "All Songs" default
    else:
        messagebox.showerror("Eroare", "User sau parola incorecte!")
        password_entry.delete(0, 'end')


# =========================================================
#               LOGICA PLAYLISTS (NOU)
# =========================================================

def creaza_playlist_nou():
    dialog = CTkInputDialog(text="Nume Playlist:", title="Playlist Nou")
    nume = dialog.get_input()
    if nume:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO playlists (nume, username) VALUES (?, ?)", (nume, current_user))
        conn.commit()
        conn.close()
        reimprospatare_sidebar_playlists()


def sterge_playlist_curent():
    if active_playlist_id is None:
        messagebox.showerror("Eroare", "Nu poti sterge Biblioteca Principala!")
        return

    raspuns = messagebox.askyesno("Confirmare", "Esti sigur ca vrei sa stergi acest playlist?")
    if raspuns:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Stergem legaturile
        c.execute("DELETE FROM playlist_songs WHERE playlist_id=?", (active_playlist_id,))
        # Stergem playlistul
        c.execute("DELETE FROM playlists WHERE id=?", (active_playlist_id,))
        conn.commit()
        conn.close()
        schimba_playlist(None)  # Revino la biblioteca
        reimprospatare_sidebar_playlists()


def adauga_in_playlist_db(playlist_id):
    try:
        # Luam melodia selectata din lista curenta
        index_selectat = lista_melodii.curselection()[0]
        id_melodie = playlist_data[index_selectat][0]  # ID din baza de date

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Verificam daca exista deja
        c.execute("SELECT * FROM playlist_songs WHERE playlist_id=? AND song_id=?", (playlist_id, id_melodie))
        if c.fetchone():
            messagebox.showinfo("Info", "Melodia este deja in playlist!")
        else:
            c.execute("INSERT INTO playlist_songs (playlist_id, song_id) VALUES (?, ?)", (playlist_id, id_melodie))
            conn.commit()
            status_label.configure(text="Melodie adaugata in playlist!")
        conn.close()
    except IndexError:
        pass


def schimba_playlist(id_playlist):
    global active_playlist_id
    active_playlist_id = id_playlist
    incarcare_melodii()

    # Update UI titlu
    if id_playlist is None:
        playlist_title_lbl.configure(text="📚 Biblioteca Mea")
        del_playlist_btn.pack_forget()  # Ascunde buton stergere pt biblioteca
    else:
        # Cauta nume playlist
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT nume FROM playlists WHERE id=?", (id_playlist,))
        res = c.fetchone()
        conn.close()
        if res:
            playlist_title_lbl.configure(text=f"📂 {res[0]}")
            del_playlist_btn.pack(side=tk.RIGHT, padx=10)  # Arata buton stergere


def reimprospatare_sidebar_playlists():
    # Sterge butoanele vechi din sidebar (inafara de titlu si buton Create)
    for widget in scrollable_playlist_frame.winfo_children():
        widget.destroy()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, nume FROM playlists WHERE username=?", (current_user,))
    playlists = c.fetchall()
    conn.close()

    # Buton pentru "All Songs"
    btn_all = ctk.CTkButton(scrollable_playlist_frame, text="📚 Toate Melodiile",
                            command=lambda: schimba_playlist(None),
                            fg_color="transparent", anchor="w", height=30)
    btn_all.pack(fill="x", pady=2)

    # Butoane pentru Playlists Custom
    for pid, pnume in playlists:
        btn = ctk.CTkButton(scrollable_playlist_frame, text=f"📂 {pnume}",
                            command=lambda i=pid: schimba_playlist(i),
                            fg_color="transparent", anchor="w", height=30)
        btn.pack(fill="x", pady=2)


# =========================================================
#               LOGICA AUDIO (ENGINE)
# =========================================================

def get_melodii(filtru_nume=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    query = ""
    params = ()

    if active_playlist_id is None:
        # --- CAZ 1: BIBLIOTECA PRINCIPALA ---
        if filtru_nume:
            query = "SELECT id, nume, cale FROM melodii WHERE username=? AND nume LIKE ?"
            params = (current_user, f"%{filtru_nume}%")
        else:
            query = "SELECT id, nume, cale FROM melodii WHERE username=?"
            params = (current_user,)
    else:
        # --- CAZ 2: PLAYLIST SPECIFIC ---
        # Facem JOIN intre melodii si playlist_songs
        if filtru_nume:
            query = """SELECT m.id, m.nume, m.cale
                       FROM melodii m
                                JOIN playlist_songs ps ON m.id = ps.song_id
                       WHERE ps.playlist_id = ? \
                         AND m.nume LIKE ?"""
            params = (active_playlist_id, f"%{filtru_nume}%")
        else:
            query = """SELECT m.id, m.nume, m.cale
                       FROM melodii m
                                JOIN playlist_songs ps ON m.id = ps.song_id
                       WHERE ps.playlist_id = ?"""
            params = (active_playlist_id,)

    c.execute(query, params)
    melodii = c.fetchall()
    conn.close()
    return melodii


def verificare_sfarsit_melodie():
    global playlist_activ
    if pygame.mixer.music.get_busy():
        root.after(100, verificare_sfarsit_melodie)
        return

    if playlist_activ and not is_paused:
        if loop_mode == 1:
            play_melodie()
        elif loop_mode == 0:
            try:
                current_index = lista_melodii.curselection()[0]
                if current_index < lista_melodii.size() - 1:
                    next_melodie()
                else:
                    stop_melodie()
            except:
                stop_melodie()
        else:
            next_melodie()


def update_progres():
    global is_dragging, lungime_melodie_curenta
    if pygame.mixer.music.get_busy() and not is_dragging:
        timp_curent_intern = pygame.mixer.music.get_pos() / 1000
        timp_total_real = timp_curent_intern + offset_timp

        if lungime_melodie_curenta > 0:
            valoare_slider = timp_total_real / lungime_melodie_curenta
            if valoare_slider > 1: valoare_slider = 1
            slider_progres.set(valoare_slider)

        time_label.configure(text=format_timp(timp_total_real))

    if playlist_activ and not is_paused:
        root.after(500, update_progres)


def play_melodie(event=None):
    global playlist_activ, lungime_melodie_curenta, offset_timp, cale_melodie_curenta, is_paused
    is_paused = False
    try:
        try:
            select_index = lista_melodii.curselection()[0]
        except IndexError:
            return

        melodie_data = playlist_data[select_index]
        nume_melodie = melodie_data[1]
        cale_melodie = melodie_data[2]

        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()

        try:
            audio_info = MP3(cale_melodie).info
            frecventa_reala = audio_info.sample_rate
            lungime_melodie_curenta = audio_info.length
            if pygame.mixer.get_init():
                pygame.mixer.quit()
            pygame.mixer.init(frequency=frecventa_reala)
        except:
            if not pygame.mixer.get_init(): pygame.mixer.init()
            lungime_melodie_curenta = obtine_durata_reala(cale_melodie)

        try:
            pygame.mixer.music.set_endevent(MUSIC_END_EVENT)
        except:
            pass

        pygame.mixer.music.load(cale_melodie)
        pygame.mixer.music.play()

        cale_melodie_curenta = cale_melodie
        pygame.mixer.music.set_volume(slider_volum.get())

        offset_timp = 0
        playlist_activ = True

        status_label.configure(text=f"🎵 Redare: {nume_melodie}")
        pauza_button.configure(text="⏸", fg_color=COLOR_ACCENT)
        play_button.configure(fg_color=("gray", "white"), text_color=COLOR_ACCENT)

        slider_progres.set(0)
        time_label.configure(text="00:00")

        update_progres()
        root.after(100, verificare_sfarsit_melodie)

    except Exception as e:
        messagebox.showerror("Eroare", f"Eroare redare: {e}")


def stop_melodie(event=None):
    global playlist_activ, cale_melodie_curenta
    pygame.mixer.music.stop()
    playlist_activ = False
    cale_melodie_curenta = ""
    status_label.configure(text="Redare oprita")
    time_label.configure(text="00:00")
    slider_progres.set(0)
    play_button.configure(fg_color=COLOR_ACCENT, text_color="white")


def pauza_melodie():
    global is_paused
    if not playlist_activ: return
    if not is_paused:
        pygame.mixer.music.pause()
        is_paused = True
        status_label.configure(text="⏸ Pauză")
        pauza_button.configure(text="▶", fg_color="orange")
    else:
        pygame.mixer.music.unpause()
        is_paused = False
        status_label.configure(text=f"🎵 Redare: {os.path.basename(cale_melodie_curenta)}")
        pauza_button.configure(text="⏸", fg_color=COLOR_ACCENT)


# =========================================================
#               CONTROALE NAVIGARE
# =========================================================

def seek_melodie(valoare):
    global offset_timp
    if lungime_melodie_curenta > 0:
        timp_target = float(valoare) * lungime_melodie_curenta
        pygame.mixer.music.set_pos(timp_target)
        offset_timp = timp_target
        time_label.configure(text=format_timp(timp_target))


def set_volum(valoare):
    pygame.mixer.music.set_volume(float(valoare))


def start_drag(event): global is_dragging; is_dragging = True


def stop_drag(event): global is_dragging; is_dragging = False; seek_melodie(slider_progres.get())


def set_selection(index):
    total_melodii = lista_melodii.size()
    if total_melodii == 0: return
    if index >= total_melodii:
        index = 0
    elif index < 0:
        index = total_melodii - 1
    lista_melodii.selection_clear(0, END)
    lista_melodii.activate(index)
    lista_melodii.select_set(index)
    play_melodie()


def next_melodie():
    global song_queue
    if len(song_queue) > 0:
        next_index = song_queue.pop(0)
        set_selection(next_index)
        return
    if shuffle_mode:
        total = lista_melodii.size()
        if total > 1:
            curr = 0
            try:
                curr = lista_melodii.curselection()[0]
            except:
                pass
            nxt = curr
            while nxt == curr: nxt = random.randint(0, total - 1)
            set_selection(nxt)
            return
    try:
        current = lista_melodii.curselection()[0]
    except:
        current = -1
    set_selection(current + 1)


def melodie_anterioara():
    try:
        current = lista_melodii.curselection()[0]
    except:
        current = 0
    set_selection(current - 1)


# =========================================================
#               MANAGER BUTOANE (ADD/DEL/LOOP/THEME)
# =========================================================

def adauga_melodie_noua():
    # Adaugam doar in biblioteca principala
    if active_playlist_id is not None:
        messagebox.showinfo("Info",
                            "Poti importa melodii noi doar in 'Biblioteca Mea', apoi le poti adauga in playlist-uri.")
        return

    cale_fisier = filedialog.askopenfilename(filetypes=[("MP3 Files", "*.mp3")])
    if not cale_fisier: return
    nume_fisier = os.path.basename(cale_fisier)
    folder_dest = os.path.join(os.path.dirname(__file__), "fisiere")
    if not os.path.exists(folder_dest): os.makedirs(folder_dest)
    cale_noua = os.path.join(folder_dest, nume_fisier)

    if os.path.abspath(cale_fisier) != os.path.abspath(cale_noua):
        try:
            shutil.copy(cale_fisier, cale_noua)
        except Exception as e:
            messagebox.showerror("Eroare", f"Nu s-a putut copia: {e}"); return

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO melodii (nume, cale, username) VALUES (?, ?, ?)",
                  (nume_fisier, cale_noua, current_user))
        conn.commit()
        conn.close()
        incarcare_melodii()
    except sqlite3.Error as e:
        messagebox.showerror("Eroare DB", str(e))


def sterge_melodie():
    try:
        idx = lista_melodii.curselection()[0]
        data = playlist_data[idx]

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        if active_playlist_id is None:
            # Sterge complet din biblioteca si de pe hard disk
            if data[2] == cale_melodie_curenta: stop_melodie()
            # Mai intai stergem din tabelele de legatura
            c.execute("DELETE FROM playlist_songs WHERE song_id=?", (data[0],))
            # Apoi din melodii
            c.execute("DELETE FROM melodii WHERE id=?", (data[0],))
        else:
            # Sterge doar din playlist-ul curent
            c.execute("DELETE FROM playlist_songs WHERE playlist_id=? AND song_id=?", (active_playlist_id, data[0]))

        conn.commit()
        conn.close()
        incarcare_melodii()
    except:
        messagebox.showerror("Eroare", "Selecteaza o melodie!")


def toggle_shuffle():
    global shuffle_mode
    shuffle_mode = not shuffle_mode
    if shuffle_mode:
        shuffle_button.configure(fg_color=COLOR_ACCENT, text="🔀 ON")
    else:
        shuffle_button.configure(fg_color="gray", text="🔀 OFF")


def toggle_loop():
    global loop_mode
    loop_mode = (loop_mode + 1) % 3
    if loop_mode == 0:
        loop_button.configure(text="🔁 OFF", fg_color="gray")
    elif loop_mode == 1:
        loop_button.configure(text="🔂 ONE", fg_color=COLOR_ACCENT)
    else:
        loop_button.configure(text="🔁 ALL", fg_color="purple")


# --- SCHIMBARE DARK/LIGHT MODE ---
def schimba_tema_fundal():
    mode = ctk.get_appearance_mode()
    if mode == "Dark":
        ctk.set_appearance_mode("Light")
        theme_bg_btn.configure(text="🌙 Dark")
        lista_melodii.config(bg=COLOR_BG_LIST[0], fg=COLOR_TEXT_LIST[0])
    else:
        ctk.set_appearance_mode("Dark")
        theme_bg_btn.configure(text="☀️ Light")
        lista_melodii.config(bg=COLOR_BG_LIST[1], fg=COLOR_TEXT_LIST[1])


def schimba_culoare_accent(alegere):
    global COLOR_ACCENT
    COLOR_ACCENT = THEME_COLORS[alegere]
    slider_progres.configure(progress_color=COLOR_ACCENT)
    lista_melodii.config(selectbackground=COLOR_ACCENT)
    if playlist_activ:
        play_button.configure(text_color=COLOR_ACCENT)
        pauza_button.configure(fg_color=COLOR_ACCENT)
    if shuffle_mode: shuffle_button.configure(fg_color=COLOR_ACCENT)
    if loop_mode == 1: loop_button.configure(fg_color=COLOR_ACCENT)


def incarcare_melodii(event=None):
    global playlist_data
    text_cautat = search_entry.get()
    lista_melodii.delete(0, END)
    playlist_data = get_melodii(text_cautat)

    # Construim meniul de adaugare in playlist dinamic
    meniu_add_playlist.delete(0, END)

    # Fetch playlist names
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, nume FROM playlists WHERE username=?", (current_user,))
    toate_playlisturile = c.fetchall()
    conn.close()

    if not toate_playlisturile:
        meniu_add_playlist.add_command(label="(Niciun Playlist Creat)", state="disabled")
    else:
        for pid, pnume in toate_playlisturile:
            # Folosim lambda cu parametru default pentru a salva pid-ul
            meniu_add_playlist.add_command(label=f"📂 {pnume}", command=lambda i=pid: adauga_in_playlist_db(i))

    for index, (id_db, nume, cale) in enumerate(playlist_data):
        lista_melodii.insert(END, f"{index + 1}. {nume}")


# =========================================================
#               MANAGER COADA
# =========================================================
def deschide_manager_coada():
    w = ctk.CTkToplevel(root)
    w.title("Manager Coadă")
    w.geometry("400x400")
    ctk.CTkLabel(w, text="Melodii ce urmează:", font=("Arial", 16, "bold")).pack(pady=10)
    lst = Listbox(w, width=50, height=15)
    lst.pack(pady=5, padx=10)

    def refresh():
        lst.delete(0, END)
        if not song_queue:
            lst.insert(END, "(Coada goală)")
        else:
            for i, idx in enumerate(song_queue):
                try:
                    lst.insert(END, f"{i + 1}. {playlist_data[idx][1]}")
                except:
                    pass

    def sterge():
        try:
            sel = lst.curselection()[0]
            if song_queue: del song_queue[sel]; refresh()
        except:
            pass

    ctk.CTkButton(w, text="Sterge selectia", command=sterge, fg_color="darkred").pack(pady=10)
    refresh()


def adauga_la_coada_selectie():
    try:
        sel = lista_melodii.curselection()[0];
        song_queue.append(sel);
        status_label.configure(
            text=f"Adaugat in coada: {playlist_data[sel][1]}")
    except:
        pass


def arata_meniu_contextual(event):
    meniu_contextual.tk_popup(event.x_root, event.y_root)


# =========================================================
#               INTERFATA GRAFICA (GUI)
# =========================================================

root = ctk.CTk()
root.title("MP3 Player Modern")
root.geometry("900x650")  # Marim putin fereastra pentru sidebar

root.bind('<space>', lambda e: pauza_melodie())

# --- LAYOUT PRINCIPAL (Split Screen) ---
main_container = ctk.CTkFrame(root, fg_color="transparent")
main_container.pack(fill=tk.BOTH, expand=True)

# 1. SIDEBAR (STANGA)
sidebar = ctk.CTkFrame(main_container, width=200, corner_radius=0)
sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=0, pady=0)

ctk.CTkLabel(sidebar, text="MP3 PLAYER", font=("Arial", 20, "bold")).pack(pady=20)
ctk.CTkButton(sidebar, text="➕ Playlist Nou", command=creaza_playlist_nou, fg_color="#444").pack(pady=10, padx=10)

ctk.CTkLabel(sidebar, text="PLAYLISTS", font=("Arial", 12), text_color="gray").pack(pady=(20, 5), anchor="w", padx=10)

scrollable_playlist_frame = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
scrollable_playlist_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

# 2. CONTINUT (DREAPTA)
content_frame = ctk.CTkFrame(main_container, fg_color="transparent")
content_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

# --- HEADER PLAYLIST CURENT ---
header_frame = ctk.CTkFrame(content_frame, fg_color="transparent", height=40)
header_frame.pack(fill=tk.X, padx=20, pady=(10, 0))
playlist_title_lbl = ctk.CTkLabel(header_frame, text="📚 Biblioteca Mea", font=("Arial", 18, "bold"))
playlist_title_lbl.pack(side=tk.LEFT)

del_playlist_btn = ctk.CTkButton(header_frame, text="🗑 Sterge Playlist", command=sterge_playlist_curent,
                                 fg_color="#8B0000", height=25, width=100)
# Se afiseaza doar cand nu e biblioteca principala

# Search Bar
search_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
search_frame.pack(fill=tk.X, padx=20, pady=(10, 10))
search_entry = ctk.CTkEntry(search_frame, placeholder_text="🔍 Caută melodie...", height=35)
search_entry.pack(fill=tk.X)
search_entry.bind("<KeyRelease>", incarcare_melodii)

# Lista Melodii
lista_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
lista_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
lista_melodii = Listbox(lista_frame, bg=COLOR_BG_LIST[1], fg=COLOR_TEXT_LIST[1],
                        selectbackground=COLOR_ACCENT, selectforeground="white",
                        font=("Arial", 12), borderwidth=0, highlightthickness=0)
lista_melodii.pack(fill=tk.BOTH, expand=True)

scrollbar = ctk.CTkScrollbar(lista_melodii, command=lista_melodii.yview)
lista_melodii.configure(yscrollcommand=scrollbar.set)
lista_melodii.bind("<Double-Button-1>", play_melodie)
lista_melodii.bind("<Button-3>", arata_meniu_contextual)

# --- MENIURI CONTEXTUALE (Click Dreapta) ---
meniu_contextual = tk.Menu(root, tearoff=0)
meniu_contextual.add_command(label="▶ Redă", command=play_melodie)
meniu_contextual.add_separator()
meniu_contextual.add_command(label="⏱ Adaugă la Coadă", command=adauga_la_coada_selectie)

# Sub-meniu pentru adaugare in playlist
meniu_add_playlist = tk.Menu(meniu_contextual, tearoff=0)
meniu_contextual.add_cascade(label="➕ Adaugă în Playlist...", menu=meniu_add_playlist)

meniu_contextual.add_separator()
meniu_contextual.add_command(label="❌ Sterge", command=sterge_melodie)

# 3. PLAYER CONTROLS
control_frame = ctk.CTkFrame(content_frame, fg_color=COLOR_BG_CARD, corner_radius=20)
control_frame.pack(pady=20, padx=20, fill=tk.X, side=tk.BOTTOM)

# A. Timeline
timeline_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
timeline_frame.pack(fill=tk.X, padx=20, pady=(15, 5))
time_label = ctk.CTkLabel(timeline_frame, text="00:00", font=("Arial", 12, "bold"))
time_label.pack(side=tk.RIGHT)
slider_progres = ctk.CTkSlider(timeline_frame, from_=0, to=1, height=16,
                               progress_color=COLOR_ACCENT, button_color="white")
slider_progres.set(0)
slider_progres.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
slider_progres.bind("<Button-1>", start_drag)
slider_progres.bind("<ButtonRelease-1>", stop_drag)

# B. Main Buttons
buttons_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
buttons_frame.pack(pady=5)

anterior = ctk.CTkButton(buttons_frame, text="⏮", command=melodie_anterioara, width=40, fg_color="transparent",
                         hover_color="#444")
anterior.grid(row=0, column=0, padx=10)
play_button = ctk.CTkButton(buttons_frame, text="▶", command=play_melodie, width=60, height=60,
                            corner_radius=30, fg_color=COLOR_ACCENT, font=("Arial", 24))
play_button.grid(row=0, column=1, padx=15)
pauza_button = ctk.CTkButton(buttons_frame, text="⏸", command=pauza_melodie, width=40, fg_color="transparent",
                             hover_color="#444")
pauza_button.grid(row=0, column=2, padx=10)
next_button = ctk.CTkButton(buttons_frame, text="⏭", command=next_melodie, width=40, fg_color="transparent",
                            hover_color="#444")
next_button.grid(row=0, column=3, padx=10)

# C. Tools
extras_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
extras_frame.pack(fill=tk.X, padx=20, pady=(10, 20))

ctk.CTkLabel(extras_frame, text="🔊").pack(side=tk.LEFT, padx=(0, 5))
slider_volum = ctk.CTkSlider(extras_frame, from_=0, to=1, command=set_volum, width=80, height=10,
                             progress_color="white")
slider_volum.set(0.5)
slider_volum.pack(side=tk.LEFT)

extra_row_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
extra_row_frame.pack(fill=tk.X, padx=10, pady=5)

del_btn = ctk.CTkButton(extra_row_frame, text="🗑", command=sterge_melodie, width=30, fg_color="#FF4444")
del_btn.pack(side=tk.LEFT, padx=2)
ToolTip(del_btn, "Sterge din playlist sau biblioteca")

add_btn = ctk.CTkButton(extra_row_frame, text="➕", command=adauga_melodie_noua, width=30, fg_color="gray")
add_btn.pack(side=tk.LEFT, padx=2)
ToolTip(add_btn, "Importa Melodii (Doar in Biblioteca)")

shuffle_button = ctk.CTkButton(extra_row_frame, text="🔀 OFF", command=toggle_shuffle, width=50, fg_color="gray")
shuffle_button.pack(side=tk.LEFT, padx=2)

loop_button = ctk.CTkButton(extra_row_frame, text="🔁 OFF", command=toggle_loop, width=50, fg_color="gray")
loop_button.pack(side=tk.LEFT, padx=2)

coada_btn = ctk.CTkButton(extra_row_frame, text="☰", command=deschide_manager_coada, width=30, fg_color="#555555")
coada_btn.pack(side=tk.LEFT, padx=2)

theme_frame = ctk.CTkFrame(extra_row_frame, fg_color="transparent")
theme_frame.pack(side=tk.RIGHT)
theme_dropdown = ctk.CTkOptionMenu(theme_frame, values=list(THEME_COLORS.keys()),
                                   command=schimba_culoare_accent, width=100)
theme_dropdown.set("Spotify Green")
theme_dropdown.pack(side=tk.RIGHT, padx=2)
theme_bg_btn = ctk.CTkButton(theme_frame, text="☀️ Light", command=schimba_tema_fundal, width=60, fg_color="gray")
theme_bg_btn.pack(side=tk.RIGHT, padx=2)

status_label = ctk.CTkLabel(content_frame, text="Asteptare...", text_color="gray")
status_label.pack(side=tk.BOTTOM, pady=5)


# =========================================================
#               STARTUP
# =========================================================

def create_mainloop():
    global username_entry, password_entry, login_window
    login_window = ctk.CTkToplevel(root)
    login_window.title("Autentificare")
    login_window.geometry("300x350")
    login_window.bind('<Return>', login)

    ctk.CTkLabel(login_window, text="User:").pack(pady=(10, 0))
    username_entry = ctk.CTkEntry(login_window)
    username_entry.pack(pady=5)
    ctk.CTkLabel(login_window, text="Parola:").pack(pady=(10, 0))
    password_entry = ctk.CTkEntry(login_window, show="*")
    password_entry.pack(pady=5)
    ctk.CTkButton(login_window, text="logare", command=login, fg_color=THEME_COLORS["Spotify Green"]).pack(pady=20)

    def register_cmd():
        u = username_entry.get();
        p = password_entry.get()
        if not u or not p: messagebox.showwarning("!", "Completeaza campurile"); return
        s, m = inregistrare_user(u, p)
        if s:
            messagebox.showinfo("OK", m)
        else:
            messagebox.showerror("Err", m)

    ctk.CTkButton(login_window, text="Inregistrare", command=register_cmd, fg_color="blue").pack(pady=5)
    root.withdraw()
    root.mainloop()


if __name__ == "__main__":
    create_mainloop()