from flask import Flask, request, jsonify, render_template
from flask_caching import Cache
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
import requests
import os
from dotenv import load_dotenv
import time
from celery import Celery
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.debug("Debug message here")

request_data = youtube.videos().list(part="snippet,contentDetails", id=video_id)
response = request_data.execute()
print("YouTube API Response:", response)


# Load environment variables
load_dotenv('YouTubeAPIkey.env')

app = Flask(__name__)

# Load API keys
HUGGING_FACE_API_KEY = os.getenv('HUGGING_FACE_API_KEY')
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

# Initialize API clients
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
headers = {"Authorization": f"Bearer {HUGGING_FACE_API_KEY}"}

# Flask-Caching configuration
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# Celery configuration
celery = Celery(app.name, broker='redis://localhost:6379/0')

# Home route
@app.route('/')
def index():
    return render_template('YouTube_Summarizer.html')

# Helper function to extract video ID
def extract_video_id(youtube_url):
    if "youtu.be" in youtube_url:
        return youtube_url.split('/')[-1].split('?')[0]
    elif "youtube.com/watch?v=" in youtube_url:
        return youtube_url.split("v=")[-1].split('&')[0]
    elif "youtube.com/embed/" in youtube_url:
        return youtube_url.split('/embed/')[-1].split('?')[0]
    return None

# Route: Fetch video information
@app.route('/video_info', methods=['POST'])
def get_video_info():
    try:
        data = request.get_json()
        youtube_url = data.get('url')
        if not youtube_url:
            return jsonify({"error": "No YouTube URL provided"}), 400

        video_id = extract_video_id(youtube_url)
        if not video_id:
            return jsonify({"error": "Invalid YouTube URL format"}), 400

        request_data = youtube.videos().list(part="snippet,contentDetails", id=video_id)
        response = request_data.execute()
        if "items" in response and response["items"]:
            video = response["items"][0]
            return jsonify({
                "title": video["snippet"]["title"],
                "author": video["snippet"]["channelTitle"],
                "duration": video["contentDetails"]["duration"],
                "thumbnail_url": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                "youtube_link": f"https://www.youtube.com/watch?v={video_id}"
            })
        return jsonify({"error": "Video not found or unable to retrieve metadata"}), 404
    except Exception as e:
        print(f"Error in /video_info: {e}")
        return jsonify({"error": "Failed to fetch video information."}), 500

# Route: Fetch full transcript
@app.route('/full_transcript', methods=['POST'])
def full_transcript():
    try:
        data = request.get_json()
        youtube_url = data.get('url')
        if not youtube_url:
            return jsonify({"error": "No YouTube URL provided"}), 400

        video_id = extract_video_id(youtube_url)
        if not video_id:
            return jsonify({"error": "Invalid YouTube URL format"}), 400

        transcript = fetch_transcript_with_backoff(video_id)
        if not transcript:
            return jsonify({"error": "Transcript not available."}), 400

        full_text = " ".join([entry['text'] for entry in transcript])
        return jsonify({"transcript": full_text})
    except Exception as e:
        print(f"Error in /full_transcript: {e}")
        return jsonify({"error": "Failed to fetch transcript."}), 500

# Route: Summarize transcript
@app.route('/summarize', methods=['POST'])
@cache.cached(timeout=300, query_string=True)
def summarize_youtube_video():
    try:
        data = request.get_json()
        youtube_url = data.get('url')
        if not youtube_url:
            return jsonify({"error": "No YouTube URL provided"}), 400

        video_id = extract_video_id(youtube_url)
        if not video_id:
            return jsonify({"error": "Invalid YouTube URL format"}), 400

        task = process_transcript.apply_async(args=[video_id])
        return jsonify({"task_id": task.id}), 202
    except Exception as e:
        print(f"Error in /summarize: {e}")
        return jsonify({"error": "Failed to process summary task."}), 500

# Helper function to fetch transcript with retries
def fetch_transcript_with_backoff(video_id, retries=3):
    delay = 2
    for attempt in range(retries):
        try:
            return YouTubeTranscriptApi.get_transcript(video_id)
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(delay)
            delay *= 2
    print("Failed to fetch transcript after retries.")
    return None

# Helper function to split text for summarization
def split_text(text, max_words=500, overlap=50):
    words = text.split()
    for i in range(0, len(words), max_words - overlap):
        yield " ".join(words[i:i + max_words])

# Helper function to summarize text
def summarize_text(text):
    try:
        response = requests.post(API_URL, headers=headers, json={"inputs": text})
        if response.status_code == 200:
            return response.json()[0]['summary_text']
        print(f"Summarization error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error during summarization: {e}")
    return None

# Celery task: Process transcript and summarize
@celery.task
def process_transcript(video_id):
    try:
        transcript = fetch_transcript_with_backoff(video_id)
        if not transcript:
            return {"error": "Transcript not available."}

        full_text = " ".join([entry['text'] for entry in transcript])
        chunk_summaries = [summarize_text(chunk) for chunk in split_text(full_text)]
        summary = " ".join(filter(None, chunk_summaries))
        return {"transcript": full_text, "summary": summary}
    except Exception as e:
        print(f"Error in Celery task: {e}")
        return {"error": "Failed to process transcript or summarize."}

if __name__ == '__main__':
    app.run(debug=True)