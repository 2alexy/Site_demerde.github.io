"""Hitster with Spotify playback (needs Premium + an open Spotify app/device).

Setup:
    pip install spotipy
    export SPOTIPY_CLIENT_ID=smth
    export SPOTIPY_CLIENT_SECRET=smth
    export SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback   # also add it in your app's dashboard

IMPORTANT (Spotify Feb 2026 rules): playlist items are only readable for
playlists YOU own or collaborate on. So copy any public playlist into your own.
"""
import random
import threading

import spotipy
from spotipy.oauth2 import SpotifyOAuth

CARDS_TO_WIN = 10
CLIP_SECONDS = 20
SCOPE = "user-read-playback-state user-modify-playback-state playlist-read-private"

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id="smth",
    client_secret="smth",
    redirect_uri="http://127.0.0.1:8888/callback",
    scope=SCOPE,
))
_timer = None


def get_playlist_songs(playlist_id):
    """Read all tracks of one of YOUR playlists via the new /items endpoint."""
    songs, offset = [], 0
    while True:
        # spotipy's playlist_items() still hits the removed /tracks route -> raw call
        page = sp._get(f"playlists/{playlist_id}/items", limit=50, offset=offset)
        for entry in page["items"]:
            t = entry.get("item") or entry.get("track")  # field renamed in 2026
            if not t or t.get("is_local") or not t.get("duration_ms"):
                continue
            songs.append({
                "title": t["name"],
                "artist": t["artists"][0]["name"],
                "year": int(t["album"]["release_date"][:4]),
                "uri": t["uri"],
                "duration_ms": t["duration_ms"],
            })
        if not page.get("next"):
            return songs
        offset += 50


def pick_device():
    devices = sp.devices()["devices"]
    if not devices:
        raise SystemExit("No active Spotify device. Open Spotify on your phone/PC and play anything once.")
    active = [d for d in devices if d["is_active"]]
    return (active or devices)[0]["id"]


def play_clip(song, device_id):
    """Start at a random position, auto-pause after CLIP_SECONDS."""
    global _timer
    if _timer:
        _timer.cancel()
    max_start = max(0, song["duration_ms"] - (CLIP_SECONDS + 5) * 1000)
    start = random.randint(0, max_start)
    sp.start_playback(device_id=device_id, uris=[song["uri"]], position_ms=start)
    _timer = threading.Timer(CLIP_SECONDS, lambda: safe_pause(device_id))
    _timer.start()


def safe_pause(device_id):
    try:
        sp.pause_playback(device_id=device_id)
    except spotipy.SpotifyException:
        pass


def is_valid_slot(timeline, slot, year):
    before_ok = slot == 0 or timeline[slot - 1]["year"] <= year
    after_ok = slot == len(timeline) or year <= timeline[slot]["year"]
    return before_ok and after_ok


def show_timeline(timeline):
    print("\n  Your timeline:")
    for i, s in enumerate(timeline):
        print(f"   [{i}] ---")
        print(f"       {s['year']}  {s['title']} - {s['artist']}")
    print(f"   [{len(timeline)}] ---")


def ask_slot(timeline, song, device_id):
    while True:
        raw = input(f"\n  Slot (0-{len(timeline)}), 'r' to replay: ").strip().lower()
        if raw == "r":
            play_clip(song, device_id)
        elif raw.isdigit() and 0 <= int(raw) <= len(timeline):
            return int(raw)
        else:
            print("  Invalid input.")


def main():
    playlist_id = input("Playlist ID or URL (must be YOURS): ").strip()
    playlist_id = playlist_id.split("playlist/")[-1].split("?")[0]
    songs = get_playlist_songs(playlist_id)
    random.shuffle(songs)
    print(f"{len(songs)} songs loaded.")

    device_id = pick_device()
    n = int(input("Number of players: ") or 1)
    names = [input(f"Name of player {i + 1}: ") or f"P{i + 1}" for i in range(n)]
    timelines = {name: [songs.pop()] for name in names}

    turn = 0
    while songs:
        name = names[turn % n]
        timeline = timelines[name]
        song = songs.pop()

        print(f"\n===== {name}'s turn ({len(timeline)}/{CARDS_TO_WIN} cards) =====")
        show_timeline(timeline)
        play_clip(song, device_id)
        slot = ask_slot(timeline, song, device_id)
        if _timer:
            _timer.cancel()
        safe_pause(device_id)

        if is_valid_slot(timeline, slot, song["year"]):
            print(f"\n  ✅ Correct! {song['title']} - {song['artist']} ({song['year']})")
            timeline.insert(slot, song)
        else:
            print(f"\n  ❌ Nope. {song['title']} - {song['artist']} ({song['year']})")

        if len(timeline) >= CARDS_TO_WIN:
            print(f"\n🏆 {name} wins!")
            return
        turn += 1
    print("\nNo more songs. Game over.")


if __name__ == "__main__":
    main()
  
