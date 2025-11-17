import pygame
import sqlite3
import os
import tkinter as tk #importam tkinter pentru listbox
import customtkinter as ctk #interfata moderna
from tkinter import Listbox,Button,END, messagebox,Frame,Label #widget uri
from customtkinter import CTkFrame

#construim o cale absoluta catre fisierul bazei de date
DB_PATH = os.path.join(os.path.dirname(__file__), "music.db")

pygame.mixer.init()  # inițializează modul audio
playlist_activ=False
def autentificare(username,password):
#verifica datele de logare in baza de date user.db
    DB_NAME="users.db"
    try:
        conn=sqlite3.connect(DB_NAME)
        c=conn.cursor()
        #cauta o potrivire cu cele "hardcodate"
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username,password))
        user_record=c.fetchone() #preluam utilizatorul
        conn.close()
        if user_record:
            return True #autentificare reusita
        else:
            return False #autentificare gresita
    except sqlite3.Error as e:
        #returneaza erori sql
        print(f"Eroare SQLite la autentificare:{e}")
        return False
def login():
    #fuctie pentru logare(cand se apasa butonul login)
    username = username_entry.get() #username_entry este o variabila globala
                                    #ce poate fi schimbata si este declarata in create_mainloop
    password = password_entry.get()
    if autentificare(username,password):
        login_window.destroy() #daca se reuseste logarea, se inchide fereastra de login

        root.deiconify() #inchide pagina de logare si afiseaza player-ul
        incarcare_melodii()
    else:
        messagebox.showerror("Eroare", "Nume utilizator sau parola incorecte!")
        password_entry.delete(0,'end') #se goleste campul de melodii

def get_melodii():
    #extragem melodii din baza de date
    conn = sqlite3.connect(DB_PATH) #aici stabilim conexiunea cu baza de date
    c = conn.cursor() #creeaza un cursor pentru a executa comenzi sql

    #alegem id-ul,numele si calea fiecarei melodii din tabelul 'melodii'
    c.execute("SELECT id, nume, cale FROM melodii")
    melodii = c.fetchall() #preluam toate datele intr-o lista de tupluri
    conn.close() #inchidem conexiunea
    return melodii #returnam lista cu melodii
def verificare_sfarsit_melodie():
    #verifica daca melodia s a terminat la fiecare 100ms
    global playlist_activ
    if pygame.mixer.music.get_busy():
        #se repeta verificarea cand se reda
        root.after(100,verificare_sfarsit_melodie)
    elif playlist_activ:
        #daca s-a terminat se trece la next
        next_melodie()

def play_melodie(event=None,):
    #functie care apeleaza butonul de play cand este apasat de utilizator
    global playlist_activ
    try:
        select_index=lista_melodii.curselection()[0] #preluam indexul melodiei selectate
        melodie_data = lista_melodii.get(select_index) #aici preluam toate datele melodiei
        nume_melodie = melodie_data[1]
        cale_melodie=melodie_data[2]
        if pygame.mixer.music.get_busy(): pygame.mixer.music.stop() #daca vreau sa redau altceva
                                                #opresc melodia curenta si o incarc si redau pe cealalta/pe care o vreau
        #incarc melodia noua si o redau
        pygame.mixer.music.load(cale_melodie)
        pygame.mixer.music.play()
        playlist_activ=True #functia de verificare functioneaza
        status_label.configure(text = f"Redare muzica: {nume_melodie}") #aici arat ce melodie ruleaza
        root.after(100,verificare_sfarsit_melodie) #asta e functie de playlist continuu

    except IndexError:
        messagebox.showerror("Eroare","Selectati o melodie din lista!")
    except pygame.error as e:
        messagebox.showerror("Eroare redare",f"Nu s-a putut reda melodia:{e}")

def stop_melodie(event=None):
    #functie care opreste redarea melodiei printr-un buton stop
    global playlist_activ
    pygame.mixer.music.stop()
    playlist_activ=False
    status_label.configure(text = "Redare oprita")
def set_selection(index):
    # Verificam limita listei(folosita de Next/Inapoi)
    total_melodii =lista_melodii.size()
    if total_melodii == 0:
        return #Daca lista e goala nu se intampla nimic
    if index >=total_melodii:
        index =0 #daca indexul depaseste limita revenim la prima melodie
    elif index < 0:
        index =total_melodii -1 #daca indexul e in limita inferioara trece la ultima melodie
    lista_melodii.selection_clear(0,END) #deselecteaza melodia dupa ce a fost selectata
    lista_melodii.activate(index)
    lista_melodii.select_set(index,last=None) #evidentiaza melodia selectata

    play_melodie()

def next_melodie():
    #calculeaza si seteaza indexul urmator pt Next
    try:
        current_index=lista_melodii.curselection()[0]
    except IndexError:
        current_index=-1
    new_index=current_index+1
    set_selection(new_index)
def melodie_anterioara():
    # calculeaza si seteaza indexul anterior pt Inapoi
    try:
        current_index=lista_melodii.curselection()[0]
    except IndexError:
        current_index=0
    new_index=current_index-1
    set_selection(new_index)

def incarcare_melodii():
    #incarca toate melodiile din baza de date in interfata Listbox
    lista_melodii.delete(0,END) #sterge ce era afisat anterior
    melodii=get_melodii() #preluam alte melodii
    if not melodii:
        messagebox.showwarning("Eroare","Baza de date este goala!")
    for id_melodie,nume_melodie, cale_melodie in melodii:
        lista_melodii.insert(END, (id_melodie,nume_melodie,cale_melodie))


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

root=ctk.CTk() #Fereastra principala
root.title("MP3 Player")
lista_melodii=Listbox(
    root,
    width=50,
    height=15,
    selectmode=tk.SINGLE, #selecteaza un singur element
    font=('Arial',12)
)
lista_melodii.pack(pady=10,padx=10)
lista_melodii.bind("<Double-Button-1>",play_melodie) #play la dublu click
control_frame=CTkFrame(root) #Frame este un container in care ne pozitionam butoanele si le grupam
control_frame.pack(pady=5)

anterior=ctk.CTkButton(
    control_frame,
    text="Inapoi",
    command=melodie_anterioara,
    fg_color="green",
)
anterior.grid(row=0,column=0,padx=5)

play_button=ctk.CTkButton(
    control_frame,
    text="Play",
    command=play_melodie,
    fg_color="green",
)
play_button.grid(row=0,column=1,padx=5)

stop_button=ctk.CTkButton(
    control_frame,
    text="Stop",
    command=stop_melodie,
   fg_color="red",
)
stop_button.grid(row=0,column=2,padx=5)

next_button=ctk.CTkButton(
    control_frame,
    text='Next',
    command=next_melodie,
    fg_color = "green"
)
next_button.grid(row=0,column=3,padx=5)

status_label = ctk.CTkLabel( #Label este un widget pentru a afisa textul simplu
    root,
    text="Asteapta selectia...",
    text_color="white",
    fg_color="gray",
    corner_radius=5,
    anchor=tk.W
)
status_label.pack(fill=tk.X,padx=10,pady=5) #fill=tk.X extine tot labe-ul pe axa ox

def create_mainloop():
    #Mecanismul pt logare si lansarea aplicatiei
    global username_entry,password_entry,login_window

    login_window=ctk.CTkToplevel(root)
    login_window.title("Autentificare")
    login_window.geometry("300x200")

    ctk.CTkLabel(login_window, text="Nume utilizator:").pack(pady=(10,0))
    username_entry=ctk.CTkEntry(login_window)
    username_entry.pack(pady=5,padx=20)

    ctk.CTkLabel(login_window,text="Parola:").pack(pady=(10,0))
    password_entry=ctk.CTkEntry(login_window, show="*")
    password_entry.pack(pady=5,padx=20)

    login_button=ctk.CTkButton(login_window,text="Login",command=login)
    login_button.pack(pady=5,padx=20)

    root.withdraw()
    root.mainloop()
incarcare_melodii()
if __name__=="__main__": #"butonul' de ON al programului
    create_mainloop()