from flask import render_template, request, jsonify
from app import app
import os
from .logic import download_and_prepare_audio, recognize_song

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