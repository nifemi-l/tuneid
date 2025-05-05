#!/usr/bin/env python3
import sys
import threading
import os
import subprocess 
from yt_dlp import YoutubeDL
import requests
import base64
from dotenv import load_dotenv

# Load API key from .env
load_dotenv()
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    print("Error: API_KEY not set in environment (.env)")
    sys.exit(1)

# Shazam endpoint configuration (raw PCM upload)
# - Pulse code modulation converts analog audio signals into digital ones (binary)
SHAZAM_URL = "https://shazam.p.rapidapi.com/songs/v2/detect"
HEADERS = {
    "x-rapidapi-host": "shazam.p.rapidapi.com",
    "x-rapidapi-key": API_KEY,
    "Content-Type": "text/plain",
    "Accept": "application/json"
}

# Maximum duration (seconds) for snippet
MAX_DURATION = 5  # Shazam recommends <=5s, <500KB payload

def download_and_prepare_audio(url: str, output_template: str = "audio_snippet") -> str:
    """Download best audio, extract to WAV, trim, convert to raw PCM (16-bit LE, mono, 44100 Hz) and return a path to the .raw file."""

    # Download & extract WAV
    wav_file = f"{output_template}.wav"
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
            "preferredquality": "192",
        }]
    }
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    # Trim and convert to RAW PCM
    # Construct the name of the output file ffmpeg will write the raw PCM data to
    raw_file = f"{output_template}.raw"

    # Using subprocess because it allows for the execution of commands normally ran in a shell
    subprocess.run([
        "ffmpeg", "-y",
        "-i", wav_file,
        "-t", str(MAX_DURATION),
        "-f", "s16le",
        "-acodec", "pcm_s16le",
        "-ac", "1",
        "-ar", "44100",
        raw_file
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

    # Cleanup WAV
    os.remove(wav_file)
    print(f"Prepared raw PCM snippet: {raw_file}")

    return raw_file


def recognize_song(raw_path: str) -> dict:
    """Read raw PCM file, base64-encode, send as text/plain to Shazam v2 API, and return metadata."""
    
    with open(raw_path, "rb") as f:
        b64bytes = base64.b64encode(f.read()) # Encode bc the API expects binary data to be b64 encoded

    # Convert the b64 bytes to a string for payload transmission
    payload = b64bytes.decode('ascii')

    # Make request
    resp = requests.post(SHAZAM_URL, headers=HEADERS, data=payload)
    if resp.status_code != 200:
        print(f"API Error {resp.status_code}: {resp.text}")
        sys.exit(1)

    data = resp.json()
    track = data.get("track", {})

    return {
        "title": track.get("title"),
        "artist": track.get("subtitle"),
        "album": next(iter(track.get("sections", [{}])[0].get("metadata", [{}])), {}).get("text"),
    }


def prompt_mode_flow():
    """Execute the prompting for terminal mode."""
    url = input("Enter TikTok URL: ")
    if not url.strip():
        print("URL Is Required.")
        return
    raw_file = download_and_prepare_audio(url)
    print("Recognizing track via Shazam…")
    result = recognize_song(raw_file)
    print("--- Recognition Result ---")
    for k, v in result.items():
        print(f"{k.capitalize()}: {v}")
    os.remove(raw_file)


def gui_mode_flow():
    """Execute the prompting for GUI mode."""
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
    except ImportError:
        print("Tkinter Not Available.")
        sys.exit(1)

    def on_download():
        url = entry.get().strip()
        if not url:
            messagebox.showwarning("Input Required", "Enter TikTok URL.")
            return
        progress.start()
        download_button.config(state=tk.DISABLED)
        def task():
            try:
                raw_file = download_and_prepare_audio(url)
                res = recognize_song(raw_file)
                msg = "\n".join(f"{k.capitalize()}: {v}" for k, v in res.items())
                messagebox.showinfo("Recognition Result", msg)
                os.remove(raw_file)
            except Exception as e:
                messagebox.showerror("Error", str(e))
            finally:
                progress.stop()
                download_button.config(state=tk.NORMAL)
        threading.Thread(target=task, daemon=True).start()

    root = tk.Tk()
    root.title("TikTok Audio Recognizer")
    frame = ttk.Frame(root, padding=20)
    frame.pack(fill=tk.BOTH, expand=True)
    ttk.Label(frame, text="TikTok URL:").pack(anchor=tk.W)
    entry = ttk.Entry(frame, width=40); entry.pack(fill=tk.X)
    progress = ttk.Progressbar(frame, mode='indeterminate'); progress.pack(fill=tk.X, pady=10)
    download_button = ttk.Button(frame, text="Download & Recognize", command=on_download)
    download_button.pack()
    root.mainloop()


def main(prompt_mode: bool = False, gui_mode: bool = False):
    if not (prompt_mode or gui_mode):
        print("Enable prompt_mode or gui_mode in main()."); sys.exit(1)
    if prompt_mode: prompt_mode_flow()
    if gui_mode: gui_mode_flow()

if __name__ == "__main__":
    main(prompt_mode=True, gui_mode=False)
