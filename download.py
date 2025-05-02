import sys
import threading
import os
import subprocess
from yt_dlp import YoutubeDL
import requests
from dotenv import load_dotenv

# Load API key from .env
load_dotenv()
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    print("Error: API_KEY not set in environment (.env)")
    sys.exit(1)

# Shazam endpoint configuration
SHAZAM_URL = "https://shazam.p.rapidapi.com/songs/detect"
HEADERS = {
    "x-rapidapi-host": "shazam.p.rapidapi.com",
    "x-rapidapi-key": API_KEY,
    "Content-Type": "text/plain"
}

# Maximum duration (seconds) accepted by Shazam API
MAX_DURATION = 12  # Shazam allows up to 12-second clips per request


def download_and_trim_audio(url: str, output_template: str = "extracted_audio") -> str:
    """
    Download and extract audio from TikTok URL, then trim to MAX_DURATION.
    Returns path to the trimmed WAV file.
    """
    # Step 1: Download best audio and extract to WAV
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "quiet": False,
        "no_warnings": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
            "preferredquality": "192",
        }]
    }
    with YoutubeDL(ydl_opts) as ydl:
        print(f"Downloading and extracting to {output_template}.wav …")
        ydl.download([url])

    original_wav = f"{output_template}.wav"
    if not os.path.exists(original_wav):
        print(f"Error: Expected file not found: {original_wav}")
        sys.exit(1)

    # Step 2: Trim audio to MAX_DURATION seconds
    trimmed_wav = f"{output_template}_trimmed.wav"
    cmd = [
        "ffmpeg", "-y",     # overwrite
        "-i", original_wav,
        "-t", str(MAX_DURATION),
        trimmed_wav
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        print(f"Trimmed audio to {MAX_DURATION} seconds: {trimmed_wav}")
    except subprocess.CalledProcessError as e:
        print(f"Error trimming audio: {e}", file=sys.stderr)
        sys.exit(1)

    # Cleanup original
    os.remove(original_wav)
    print(f"Deleted original file: {original_wav}")

    return trimmed_wav


def recognize_song(audio_path: str) -> dict:
    """
    Send the raw audio bytes to the Shazam RapidAPI endpoint and return parsed metadata.
    """
    with open(audio_path, "rb") as f:
        data = f.read()
    resp = requests.post(SHAZAM_URL, headers=HEADERS, data=data)
    if resp.status_code != 200:
        print(f"API Error {resp.status_code}: {resp.text}")
        sys.exit(1)
    data = resp.json()
    track = data.get("track", {})
    match = data.get("match", {})
    return {
        "title": track.get("title"),
        "artist": track.get("subtitle"),
        "album": next(iter(track.get("sections", [{}])[0].get("metadata", [{}])), {}).get("text"),
        "confidence": match.get("confidence")
    }


def prompt_mode_flow():
    """
    Prompt user for URL, download, trim, and recognize.
    """
    url = input("Enter TikTok URL: ")
    if not url.strip():
        print("URL Is Required.")
        return
    wav_file = download_and_trim_audio(url)
    print("Recognizing track via Shazam…")
    result = recognize_song(wav_file)
    print("--- Recognition Result ---")
    for k, v in result.items():
        print(f"{k.capitalize()}: {v}")
    # Optionally cleanup trimmed file
    os.remove(wav_file)
    print(f"Deleted trimmed file: {wav_file}")


def gui_mode_flow():
    """
    GUI mode: prompt, download, trim, recognize.
    """
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
    except ImportError:
        print("Tkinter Is Not Available On This System.")
        sys.exit(1)

    def on_download():
        url = entry.get().strip()
        if not url:
            messagebox.showwarning("Input Required", "Please Enter A TikTok URL.")
            return

        progress.start()
        download_button.config(state=tk.DISABLED)

        def task():
            try:
                wav_file = download_and_trim_audio(url)
                res = recognize_song(wav_file)
                msg = "\n".join(f"{k.capitalize()}: {v}" for k, v in res.items())
                messagebox.showinfo("Recognition Result", msg)
                os.remove(wav_file)
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
    entry = ttk.Entry(frame, width=40)
    entry.pack(fill=tk.X)

    progress = ttk.Progressbar(frame, mode='indeterminate')
    progress.pack(fill=tk.X, pady=10)

    download_button = ttk.Button(frame, text="Download & Recognize", command=on_download)
    download_button.pack()

    root.mainloop()


def main(prompt_mode: bool = False, gui_mode: bool = False):
    """
    Main entry. Choose a mode.
    """
    if not (prompt_mode or gui_mode):
        print("No Mode Enabled. Enable prompt_mode or gui_mode in main().")
        sys.exit(1)
    if prompt_mode:
        prompt_mode_flow()
    if gui_mode:
        gui_mode_flow()


if __name__ == "__main__":
    main(prompt_mode=True, gui_mode=False)
