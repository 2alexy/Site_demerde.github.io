"""Hitster GUI v2 - same folder as your working hitster_spotify.py.

New in v2:
  * Year check: each song's year is compared with MusicBrainz (original release date)
    and the EARLIEST one wins, so remasters/compilations stop lying to you.
  * Scrollable timeline (mouse wheel or scrollbar), compact rows.
"""
import json
import random
import re
import time
import tkinter as tk
import urllib.parse
import urllib.request
from tkinter import messagebox

import hitster_spotify as core

# MusicBrainz asks for a real contact in the User-Agent. Put yours.
MB_UA = "HitsterGame/2.0 (your-email@example.com)"
_last_mb = 0.0


# ---------- year fix ----------
def clean_title(title):
    """'Song - 2011 Remaster' / 'Song (Live)' -> 'Song'"""
    t = re.sub(
        r"\s*[-–(\[]\s*(\d{4}\s*)?(remaster|remastered|mono|stereo|live|version|edit|deluxe|single|radio|bonus)\b.*$",
        "", title, flags=re.I)
    return t.replace('"', " ").strip()


def fix_year(song):
    """Replace song['year'] with the earliest MusicBrainz date if it's earlier."""
    global _last_mb
    if song.get("checked"):
        return
    song["checked"] = True
    song["spotify_year"] = song["year"]

    wait = 1.1 - (time.time() - _last_mb)  # MusicBrainz limit: 1 request/second
    if wait > 0:
        time.sleep(wait)

    query = f'recording:"{clean_title(song["title"])}" AND artist:"{song["artist"].replace(chr(34), " ")}"'
    url = "https://musicbrainz.org/ws/2/recording?" + urllib.parse.urlencode(
        {"query": query, "fmt": "json", "limit": 15})
    try:
        req = urllib.request.Request(url, headers={"User-Agent": MB_UA})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.load(r)
    except Exception:
        return  # offline / blocked: keep Spotify's year
    finally:
        _last_mb = time.time()

    years = []
    for rec in data.get("recordings", []):
        d = rec.get("first-release-date") or ""
        if rec.get("score", 0) >= 90 and d[:4].isdigit():
            years.append(int(d[:4]))
    if years and 1900 <= min(years) < song["year"]:
        song["year"] = min(years)


# ---------- app ----------
class HitsterApp:
    def __init__(self, root):
        self.root = root
        root.title("Hitster")
        root.geometry("480x720")
        self.songs, self.names, self.timelines = [], [], {}
        self.turn, self.song, self.device_id = 0, None, None
        self.build_setup()

    # ----- setup screen -----
    def build_setup(self):
        self.setup = tk.Frame(self.root, padx=20, pady=20)
        self.setup.pack(fill="both", expand=True)
        tk.Label(self.setup, text="🎵 HITSTER", font=("Arial", 22, "bold")).pack(pady=10)

        tk.Label(self.setup, text="Playlist link (must be YOURS):").pack(anchor="w")
        self.playlist_entry = tk.Entry(self.setup, width=50)
        self.playlist_entry.pack(fill="x", pady=5)

        tk.Label(self.setup, text="Players (comma separated):").pack(anchor="w", pady=(10, 0))
        self.players_entry = tk.Entry(self.setup, width=50)
        self.players_entry.insert(0, "Player 1, Player 2")
        self.players_entry.pack(fill="x", pady=5)

        tk.Button(self.setup, text="Start game", command=self.start_game,
                  font=("Arial", 12, "bold")).pack(pady=20)
        self.status = tk.Label(self.setup, text="", fg="gray")
        self.status.pack()

    def set_status(self, text):
        self.status.config(text=text)
        self.root.update()

    def start_game(self):
        link = self.playlist_entry.get().strip()
        if not link:
            messagebox.showwarning("Hitster", "Paste a playlist link first.")
            return
        playlist_id = link.split("playlist/")[-1].split("?")[0]

        self.set_status("Loading playlist...")
        try:
            self.songs = core.get_playlist_songs(playlist_id)
            self.device_id = core.pick_device()
        except BaseException as e:  # SystemExit from pick_device included
            self.set_status("")
            messagebox.showerror("Hitster", f"Couldn't start:\n{e}")
            return

        self.names = [n.strip() for n in self.players_entry.get().split(",") if n.strip()]
        if not self.names or len(self.songs) < len(self.names) + 5:
            messagebox.showerror("Hitster", "Need 1+ players and a playlist with enough songs.")
            return

        random.shuffle(self.songs)
        self.timelines = {}
        for n in self.names:
            self.set_status(f"Checking the year of {n}'s first card...")
            card = self.songs.pop()
            fix_year(card)
            self.timelines[n] = [card]

        self.turn = 0
        self.setup.destroy()
        self.build_game()
        self.new_turn()

    # ----- game screen -----
    def build_game(self):
        self.game = tk.Frame(self.root, padx=10, pady=10)
        self.game.pack(fill="both", expand=True)

        self.title_label = tk.Label(self.game, font=("Arial", 16, "bold"))
        self.title_label.pack()

        top = tk.Frame(self.game)
        top.pack(pady=5)
        tk.Button(top, text="🔁 Replay", command=self.replay).pack(side="left", padx=5)
        tk.Label(top, text="Where does this song go?").pack(side="left", padx=5)

        # bottom bar packed BEFORE the scroll area so it never gets squeezed out
        self.bottom = tk.Frame(self.game)
        self.bottom.pack(side="bottom", fill="x")
        self.result_label = tk.Label(self.bottom, text="", font=("Arial", 12), wraplength=440)
        self.result_label.pack(pady=4)
        self.next_btn = tk.Button(self.bottom, text="Next ▶", command=self.next_turn)

        # scrollable timeline
        wrap = tk.Frame(self.game)
        wrap.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(wrap, highlightthickness=0)
        sb = tk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.timeline_frame = tk.Frame(self.canvas)
        self.cwin = self.canvas.create_window((0, 0), window=self.timeline_frame, anchor="nw")
        self.timeline_frame.bind(
            "<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.cwin, width=e.width))

        # mouse wheel: Windows/macOS use <MouseWheel>, Linux uses Button-4/5
        self.root.bind_all("<MouseWheel>", self.on_wheel)
        self.root.bind_all("<Button-4>", self.on_wheel)
        self.root.bind_all("<Button-5>", self.on_wheel)

    def on_wheel(self, e):
        if e.num == 4:
            step = -1
        elif e.num == 5:
            step = 1
        else:
            step = -1 if e.delta > 0 else 1
        self.canvas.yview_scroll(step, "units")

    def current_name(self):
        return self.names[self.turn % len(self.names)]

    def new_turn(self):
        self.next_btn.pack_forget()
        self.result_label.config(text="", fg="black")

        name = self.current_name()
        timeline = self.timelines[name]
        self.song = self.songs.pop()

        self.title_label.config(text=f"{name}  ({len(timeline)}/{core.CARDS_TO_WIN}) - checking year...")
        self.root.update()
        fix_year(self.song)
        self.title_label.config(text=f"{name}  ({len(timeline)}/{core.CARDS_TO_WIN})")

        self.draw_timeline(timeline, clickable=True)
        self.canvas.yview_moveto(0)
        self.replay()

    def draw_timeline(self, timeline, clickable):
        for w in self.timeline_frame.winfo_children():
            w.destroy()
        for i in range(len(timeline) + 1):
            tk.Button(self.timeline_frame, text="▼ here", pady=0, font=("Arial", 9),
                      state="normal" if clickable else "disabled",
                      command=lambda slot=i: self.place(slot)).pack(fill="x", padx=60, pady=1)
            if i < len(timeline):
                s = timeline[i]
                tk.Label(self.timeline_frame, text=f"{s['year']}   {s['title']} - {s['artist']}",
                         relief="groove", pady=3, anchor="w", padx=6).pack(fill="x", pady=1)

    def replay(self):
        try:
            core.play_clip(self.song, self.device_id)
        except Exception as e:
            messagebox.showerror("Hitster", f"Playback error:\n{e}")

    def place(self, slot):
        if core._timer:
            core._timer.cancel()
        core.safe_pause(self.device_id)

        name = self.current_name()
        timeline = self.timelines[name]
        s = self.song
        info = f"{s['title']} - {s['artist']} ({s['year']})"
        if s["year"] != s.get("spotify_year", s["year"]):
            info += f"\nYear corrected (Spotify said {s['spotify_year']})"

        if core.is_valid_slot(timeline, slot, s["year"]):
            timeline.insert(slot, s)
            self.result_label.config(text=f"✅ Correct!\n{info}", fg="green")
        else:
            self.result_label.config(text=f"❌ Nope.\n{info}", fg="red")

        self.draw_timeline(timeline, clickable=False)
        self.root.update_idletasks()
        self.canvas.yview_moveto(max(0.0, slot / (len(timeline) + 1) - 0.1))

        if len(timeline) >= core.CARDS_TO_WIN:
            messagebox.showinfo("Hitster", f"🏆 {name} wins!")
            self.root.destroy()
            return
        if not self.songs:
            messagebox.showinfo("Hitster", "No more songs. Game over.")
            self.root.destroy()
            return
        self.next_btn.pack(pady=4)

    def next_turn(self):
        self.turn += 1
        self.new_turn()


if __name__ == "__main__":
    root = tk.Tk()
    HitsterApp(root)
    root.mainloop()
