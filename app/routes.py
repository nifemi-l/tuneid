from flask import render_template, request, jsonify
from app import app
import os
from .logic import download_and_prepare_audio, recognize_song, download_audio, convert_to_pcm

@app.route("/", methods=["GET"])
def index(): 
    return render_template("index.html")

@app.route("/recognize", methods=["POST"])
def recognize_route(): 
    url = request.form.get("url", "").strip()
    if not url: 
        return jsonify({"error": "URL is required"}), 400
    
    raw_file = None
    try: 
        raw_file = download_and_prepare_audio(url)
        result = recognize_song(raw_file)
        return jsonify(result)
    except Exception as e: 
        return jsonify({"error": str(e)}), 500
    finally:
        if raw_file and os.path.exists(raw_file): 
            try: 
                os.remove(raw_file)
            except OSError:
                pass

@app.route("/validate-extraction", methods=["POST"])
def validate_extraction(): 
    url = request.form.get("url", "").strip()
    if not url: 
        return jsonify({"error": "URL is required"}), 400
    
    try: 
        audio_path = download_audio(url)
        if not audio_path or not os.path.exists(audio_path): 
            return jsonify({"error": "Audio extraction failed"}), 500
        return jsonify({"success": True, "path": audio_path})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/validate-processing", methods=["POST"])
def validate_processing():
    url = request.form.get("url", "").strip()
    if not url:
        return jsonify({"error": "URL is required"}), 400
    
    try:
        audio_path = download_audio(url)
        pcm_path = convert_to_pcm(audio_path)
        if not pcm_path or not os.path.exists(pcm_path):
            return jsonify({"error": "Sound processing failed"}), 500
        return jsonify({"success": True, "path": pcm_path})
    finally:
        # Clean up downloaded audio file
        if audio_path and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except OSError:
                pass