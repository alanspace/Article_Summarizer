from flask import Flask, request, jsonify, render_template
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
import requests
import os
from dotenv import load_dotenv
import time

load_dotenv('YouTubeAPIkey.env')

app = Flask(__name__)

# Load API keys
HUGGING_FACE_API_KEY = os.getenv('HUGGING_FACE_API_KEY')
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

# Initialize API clients
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
headers = {"Authorization": f"Bearer {HUGGING_FACE_API_KEY}"}

@app.route('/')
def index():
    return render_template('YouTube_Summarizer.html')

# Helper function to extract video ID
def extract_video_id(youtube_url):
    video_id = None
    if "youtu.be" in youtube_url:
        video_id = youtube_url.split('/')[-1].split('?')[0]
    elif "youtube.com/watch?v=" in youtube_url:
        video_id = youtube_url.split("v=")[-1].split('&')[0]
    elif "youtube.com/embed/" in youtube_url:
        video_id = youtube_url.split('/embed/')[-1].split('?')[0]
    print("Extracted Video ID:", video_id)
    return video_id

# Function to fetch captions availability
def get_captions_from_youtube_data_api(video_id):
    url = f"https://www.googleapis.com/youtube/v3/captions?part=snippet&videoId={video_id}&key={YOUTUBE_API_KEY}"
    response = requests.get(url)
    data = response.json()
    if 'items' in data and data['items']:
        return "Captions are available but may be restricted."
    return None

# Function to fetch video details
def fetch_video_details(video_id):
    try:
        request = youtube.videos().list(part="snippet,contentDetails", id=video_id)
        response = request.execute()
        if "items" in response and response["items"]:
            video = response["items"][0]
            return {
                "title": video["snippet"]["title"],
                "author": video["snippet"]["channelTitle"],
                "duration": video["contentDetails"]["duration"],
                "thumbnail_url": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                "youtube_link": f"https://www.youtube.com/watch?v={video_id}"
            }
    except Exception as e:
        print(f"Error fetching video details: {e}")
    return None

# Route to get video information
@app.route('/video_info', methods=['POST'])
def get_video_info():
    data = request.get_json()
    youtube_url = data.get('url')
    if not youtube_url:
        return jsonify({"error": "No YouTube URL provided"}), 400
    video_id = extract_video_id(youtube_url)
    if not video_id:
        return jsonify({"error": "Invalid YouTube URL format"}), 400
    video_details = fetch_video_details(video_id)
    if not video_details:
        return jsonify({"error": "Video not found or unable to retrieve metadata"}), 404
    video_details["captions_info"] = get_captions_from_youtube_data_api(video_id)
    return jsonify(video_details)

# Function to fetch transcript with retries
def fetch_transcript_with_backoff(video_id, retries=3):
    delay = 2
    for attempt in range(retries):
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            print("Transcript retrieved successfully")
            return transcript
        except Exception as e:
            print(f"Attempt {attempt + 1} failed with error: {e}")
            time.sleep(delay)
            delay *= 2
    print("Failed to retrieve transcript after multiple attempts.")
    return None

# Summarize text function
def summarize_text(text):
    response = requests.post(API_URL, headers=headers, json={"inputs": text})
    if response.status_code == 200:
        return response.json()[0]['summary_text']
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

    # Try local transcript retrieval with youtube-transcript-api
    transcript = fetch_transcript_with_backoff(video_id)
    if not transcript:
        # If local method fails, provide a fallback message
        captions_info = get_captions_from_youtube_data_api(video_id)
        if captions_info:
            return jsonify({"error": captions_info}), 400
        return jsonify({"error": "Transcript not available or restricted due to YouTube's settings."}), 400

    # Combine transcript into a single text
    full_text = " ".join([entry['text'] for entry in transcript])

    # Summarize the transcript
    try:
        chunk_summaries = [summarize_text(chunk) for chunk in split_text(full_text, max_words=500, overlap=50)]
        return jsonify({"summary": " ".join(filter(None, chunk_summaries))})
    except Exception as e:
        print(f"Summarization error: {e}")
        return jsonify({"error": "Could not summarize transcript"}), 500

# Helper to split text for summarization
def split_text(text, max_words=500, overlap=50):
    words = text.split()
    for i in range(0, len(words), max_words - overlap):
        yield " ".join(words[i:i + max_words])

if __name__ == '__main__':
    app.run(debug=True)