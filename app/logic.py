import os
import subprocess
import base64
import requests
from yt_dlp import YoutubeDL
from dotenv import load_dotenv
import platform
import shutil

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

def get_browser_for_cookies():
    """Detect available browsers and return the best option for cookie extraction."""
    browsers = ['chrome', 'firefox', 'edge', 'safari', 'opera']
    available_browsers = []
    system = platform.system().lower()
    
    print(f"System detected: {system}")  # DEBUG
    
    for browser in browsers:
        if system == 'windows':
            if browser == 'chrome' and shutil.which('chrome'):
                available_browsers.append('chrome')
            elif browser == 'firefox' and shutil.which('firefox'):
                available_browsers.append('firefox')
            elif browser == 'edge' and shutil.which('msedge'):
                available_browsers.append('edge')
        elif system == 'darwin':  # macOS
            if browser == 'chrome' and os.path.exists('/Applications/Google Chrome.app'):
                available_browsers.append('chrome')
            elif browser == 'firefox' and os.path.exists('/Applications/Firefox.app'):
                available_browsers.append('firefox')
            elif browser == 'safari' and os.path.exists('/Applications/Safari.app'):
                available_browsers.append('safari')
            elif browser == 'edge' and os.path.exists('/Applications/Microsoft Edge.app'):
                available_browsers.append('edge')
        else:  # Linux
            if browser == 'chrome' and (shutil.which('google-chrome') or shutil.which('chromium')):
                available_browsers.append('chrome')
                print(f"Found Chrome: {shutil.which('google-chrome') or shutil.which('chromium')}")  # DEBUG
            elif browser == 'firefox' and shutil.which('firefox'):
                available_browsers.append('firefox')
                print(f"Found Firefox: {shutil.which('firefox')}")  # DEBUG
            elif browser == 'edge' and shutil.which('microsoft-edge'):
                available_browsers.append('edge')
    
    print(f"Available browsers: {available_browsers}")  # DEBUG
    
    try: 
        return available_browsers[0]
    except: 
        return None
    
def download_audio(url: str, output_template: str = "audio_snippet") -> str:
    """Download best audio quality and extract to WAV format with cookie support."""
    wav_file = f"{output_template}.wav"

    # Base yt-dlp options
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
            "preferredquality": "192",
        }],
        # Anti-bot detection measures
        "sleep_interval": 1,
        "max_sleep_interval": 3,
        "extractor_args": {
            "youtube": {
                "player_client": ["android"],
                "skip": ["hls", "dash"]
            }
        }
    }

    # Try with browser cookies first
    browser = get_browser_for_cookies()
    if browser:
        try:
            ydl_opts_with_cookies = ydl_opts.copy()
            
            # Handle special cases for Linux Flatpak installations
            if platform.system().lower() == 'linux' and browser == 'chrome':
                flatpak_chrome_path = os.path.expanduser('~/.var/app/com.google.Chrome/')
                if os.path.exists(flatpak_chrome_path):
                    ydl_opts_with_cookies["cookiesfrombrowser"] = f"chrome:{flatpak_chrome_path}"
                else:
                    ydl_opts_with_cookies["cookiesfrombrowser"] = browser
            else:
                ydl_opts_with_cookies["cookiesfrombrowser"] = browser
            
            with YoutubeDL(ydl_opts_with_cookies) as ydl:
                ydl.download([url])
            return wav_file
            
        except Exception as e:
            print(f"Cookie method failed with {browser}, trying fallback methods...")
    
    # Fallback 1: Try without cookies but with user agent
    try:
        ydl_opts_fallback = ydl_opts.copy()
        ydl_opts_fallback["http_headers"] = { # Spoof
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        with YoutubeDL(ydl_opts_fallback) as ydl:
            ydl.download([url])
        return wav_file
        
    except Exception as e:
        print(f"Fallback method 1 failed, trying final fallback...")
    
    # Fallback 2: Basic download attempt
    try:
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return wav_file
        
    except Exception as e:
        raise ValueError(f"Audio could not be extracted from URL. All methods failed. Last error: {str(e)}")

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