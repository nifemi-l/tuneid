import os
import subprocess
import base64
import requests
from yt_dlp import YoutubeDL
from dotenv import load_dotenv

# Load API key
load_dotenv()
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise RuntimeError("API_KEY not set in environment (.env)")

# Shazam endpoint
SHAZAM_URL = "https://shazam.p.rapidapi.com/songs/v2/detect"
HEADERS = {
    "x-rapidapi-host": "shazam.p.rapidapi.com",
    "x-rapidapi-key": API_KEY,
    "Content-Type": "text/plain",
    "Accept": "application/json"
}

# Maximum duration (seconds) for snippet
MAX_DURATION = 8

def download_audio(url: str, output_template: str = "audio_snippet") -> str:
    """Download best audio quality and extract to WAV format."""
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

    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return wav_file
    except:
        raise ValueError("Audio could not be extracted from URL")

def convert_to_pcm(wav_file: str, output_template: str = "audio_snippet") -> str:
    """Convert WAV to raw PCM format with specific parameters."""
    raw_file = f"{output_template}.raw"

    try:
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
        return raw_file
    except subprocess.CalledProcessError:
        raise RuntimeError("Error processing audio")
    finally:
        # Clean up WAV file
        try:
            os.remove(wav_file)
        except OSError:
            pass

def download_and_prepare_audio(url: str, output_template: str = "audio_snippet") -> str:
    """Download best audio, extract to WAV, trim, convert to raw PCM and return raw path."""
    wav_file = download_audio(url, output_template)
    raw_file = convert_to_pcm(wav_file, output_template)
    return raw_file

def recognize_song(raw_path: str) -> dict:
    """Encode raw PCM, send to Shazam API, return metadata."""
    with open(raw_path, "rb") as f:
        payload = base64.b64encode(f.read()).decode('ascii')

    resp = requests.post(SHAZAM_URL, headers=HEADERS, data=payload, timeout=10)

    # Check for entity too large error. This should not silently fail
    if resp.status_code == 413: 
        # Payload too large
        raise RuntimeError("Audio payload exceeds Shazam's 5s limit; try a shorter clip.")
    elif not resp.ok: 
        # Other errors
        raise RuntimeError(f"API Error {resp.status_code}: {resp.text}")
    
    resp.raise_for_status()
    data = resp.json()
    track = data.get("track", {})

    # Ensure the found track is valid
    # - Precaution for silent failure
    if not track or not track.get("title") or not track.get("subtitle"): 
        raise ValueError("Song not found")
        
    # Basic track info
    # - Other pertinent information will be fed here
    result =  {
        "title": track.get("title"),
        "artist": track.get("subtitle"),
        "album": next(
            iter(track.get("sections", [{}])[0].get("metadata", [{}])),
            {}
        ).get("text"),
    }

    # Pictorial info
    images = track.get("images", {})

    # Static place holder (in case Shazam doesn't return any art)
    placeholder = "static/img/no-cover.png"
    cover = images.get("coverart") or placeholder
    cover_hq = images.get("coverarthq") or placeholder

    # print(placeholder, cover, cover_hq)

    result["images"] = {
        "background": images.get("background") or placeholder,
        "cover_art": cover,
        "cover_art_hq": cover_hq,
    }

    # Additional images from metapages
    sections = track.get("sections", [])
    song_section = next((s for s in sections if s.get("type") == "SONG"), {})
    metapages = song_section.get("metapages", [])
    result["metapage_images"] = [
        page.get("image") for page in metapages if page.get("image")
    ]

    return result