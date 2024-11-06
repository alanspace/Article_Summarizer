from flask import Flask, request, jsonify, render_template
from youtube_transcript_api import YouTubeTranscriptApi
import requests
import os
from dotenv import load_dotenv
import time

load_dotenv('APIkey.env')

app = Flask(__name__)

# Print environment variables for debugging
print("Hugging Face API Key:", os.getenv('HUGGING_FACE_API_KEY'))
print("YouTube API Key:", os.getenv('YOUTUBE_API_KEY'))

# Hugging Face API settings
API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
headers = {"Authorization": f"Bearer {os.getenv('HUGGING_FACE_API_KEY')}"}

# YouTube Data API Key
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

# Fallback function to use YouTube Data API for captions
def fetch_captions_from_youtube_data_api(video_id):
    url = f"https://www.googleapis.com/youtube/v3/captions?part=snippet&videoId={video_id}&key={YOUTUBE_API_KEY}"
    response = requests.get(url)
    data = response.json()

    if 'items' in data and data['items']:
        return "Captions available but could not be retrieved in detail due to restrictions."
    else:
        return None

# Function to fetch transcript with exponential backoff
def fetch_transcript_with_backoff(video_id, retries=3):
    delay = 2
    for attempt in range(retries):
        try:
            return YouTubeTranscriptApi.get_transcript(video_id)
        except Exception as e:
            print(f"Attempt {attempt + 1} failed with error: {e}")
            time.sleep(delay)
            delay *= 2
    return None

# Summarize text
def summarize_text(text):
    response = requests.post(API_URL, headers=headers, json={"inputs": text})
    if response.status_code == 200:
        return response.json()[0]['summary_text']
    else:
        print("Error:", response.status_code, response.text)
        return None

# Route to summarize YouTube video transcript
@app.route('/summarize', methods=['POST'])
def summarize_youtube_video():
    data = request.get_json()
    youtube_url = data.get('url')

    if not youtube_url:
        return jsonify({"error": "No YouTube URL provided"}), 400

    video_id = extract_video_id(youtube_url)
    transcript = fetch_transcript_with_backoff(video_id)

    # If transcript retrieval fails, use YouTube Data API as a fallback
    if not transcript:
        fallback_message = fetch_captions_from_youtube_data_api(video_id)
        if fallback_message:
            return jsonify({"error": fallback_message}), 400
        else:
            return jsonify({"error": "Transcript not available or restricted due to YouTube's settings."}), 400

    full_text = " ".join([entry['text'] for entry in transcript])

    # Summarize the transcript
    try:
        chunk_summaries = [summarize_text(chunk) for chunk in split_text(full_text, max_words=500, overlap=50)]
        combined_summary = " ".join(filter(None, chunk_summaries))
        return jsonify({"summary": combined_summary})
    except Exception as e:
        print(f"Summarization error: {e}")
        return jsonify({"error": "Could not summarize transcript"}), 500

# Helper function to extract video ID
def extract_video_id(youtube_url):
    if "youtu.be" in youtube_url:
        return youtube_url.split('/')[-1].split('?')[0]
    elif "youtube.com/watch?v=" in youtube_url:
        return youtube_url.split("v=")[-1].split('&')[0]
    elif "youtube.com/embed/" in youtube_url:
        return youtube_url.split('/embed/')[-1].split('?')[0]
    return None

# Function to split long text for summarization
def split_text(text, max_words=500, overlap=50):
    words = text.split()
    for i in range(0, len(words), max_words - overlap):
        yield " ".join(words[i:i + max_words])

if __name__ == '__main__':
    app.run(debug=True)