from flask import Flask, request, jsonify, render_template
from youtube_transcript_api import YouTubeTranscriptApi
import requests

app = Flask(__name__)

# API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
# headers = {"Authorization": ""}  # Replace with your key

import os

API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
headers = {"Authorization": f"Bearer {os.getenv('HUGGING_FACE_API_KEY')}"}

def summarize_text(text):
    response = requests.post(API_URL, headers=headers, json={"inputs": text})
    if response.status_code == 200:
        return response.json()[0]['summary_text']
    else:
        return None

def split_text(text, max_words=500, overlap=50):
    words = text.split()
    for i in range(0, len(words), max_words - overlap):
        yield " ".join(words[i:i + max_words])

@app.route('/')
def index():
    return render_template('YouTube_Summarizer.html')

@app.route('/summarize', methods=['POST'])
def summarize_youtube_video():
    data = request.get_json()
    youtube_url = data.get('url')
    
    if not youtube_url:
        return jsonify({"error": "No YouTube URL provided"}), 400

    try:
        video_id = youtube_url.split("v=")[-1]
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        full_text = " ".join([entry['text'] for entry in transcript])
        
    except Exception as e:
        print(f"Transcript retrieval error: {e}")
        return jsonify({"error": "This video does not have a transcript available."}), 400

    # Proceed with summarizing the transcript if retrieval is successful
    try:
        chunk_summaries = [summarize_text(chunk) for chunk in split_text(full_text, max_words=500, overlap=50)]
        combined_summary = " ".join(filter(None, chunk_summaries))
        return jsonify({"summary": combined_summary})
    except Exception as e:
        print(f"Summarization error: {e}")
        return jsonify({"error": "Could not summarize transcript"}), 500

@app.route('/test_youtube', methods=['GET'])
def test_youtube():
    try:
        response = requests.get("https://www.youtube.com/")
        if response.status_code == 200:
            return "YouTube is accessible from this server."
        else:
            return f"Failed to access YouTube: Status Code {response.status_code}"
    except Exception as e:
        return f"Error accessing YouTube: {e}"

from youtube_transcript_api._errors import TranscriptNotFound, NoTranscriptAvailable

try:
    transcript = YouTubeTranscriptApi.get_transcript(video_id)
    full_text = " ".join([entry['text'] for entry in transcript])
except TranscriptNotFound:
    print("Transcript not found for this video.")
    return jsonify({"error": "Transcript not available due to YouTube restrictions."}), 400
except NoTranscriptAvailable:
    print("No transcript available.")
    return jsonify({"error": "No captions available for this video."}), 400
except Exception as e:
    print(f"General transcript retrieval error: {e}")
    return jsonify({"error": "An error occurred retrieving the transcript."}), 500

if __name__ == '__main__':
    app.run(debug=True)


    
