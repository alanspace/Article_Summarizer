from flask import Flask, request, jsonify, render_template
from youtube_transcript_api import YouTubeTranscriptApi
import requests
import os
from dotenv import load_dotenv
import time

load_dotenv('APIkey.env')

app = Flask(__name__)

# Print environment variables
print("Hugging Face API Key:", os.getenv('HUGGING_FACE_API_KEY'))
print("YouTube API Key:", os.getenv('YOUTUBE_API_KEY'))

# Hugging Face API settings
API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
headers = {"Authorization": f"Bearer {os.getenv('HUGGING_FACE_API_KEY')}"}

# YouTube Data API Key from environment variable
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

def fetch_transcript_with_backoff(video_id, retries=3):
    delay = 2  # Initial delay in seconds
    for attempt in range(retries):
        try:
            return YouTubeTranscriptApi.get_transcript(video_id)
        except Exception as e:  # Catch any exception if TranscriptNotFound is not explicitly accessible
            print(f"Attempt {attempt + 1} failed with error: {e}")
            time.sleep(delay)
            delay *= 2  # Exponential backoff
    print("Failed to retrieve transcript after multiple attempts.")
    return None

# Function to summarize text
def summarize_text(text):
    response = requests.post(API_URL, headers=headers, json={"inputs": text})
    if response.status_code == 200:
        return response.json()[0]['summary_text']
    else:
        print("Error:", response.status_code, response.text)
        return None

# Split long text into chunks for summarization
def split_text(text, max_words=500, overlap=50):
    words = text.split()
    for i in range(0, len(words), max_words - overlap):
        yield " ".join(words[i:i + max_words])

# Route for the main page
@app.route('/')
def index():
    return render_template('YouTube_Summarizer.html')

# Use this function in the summarize_youtube_video route
@app.route('/summarize', methods=['POST'])
def summarize_youtube_video():
    data = request.get_json()
    youtube_url = data.get('url')
    
    if not youtube_url:
        return jsonify({"error": "No YouTube URL provided"}), 400

    video_id = extract_video_id(youtube_url)
    transcript = fetch_transcript_with_backoff(video_id)
    
    if not transcript:
        return jsonify({"error": "Transcript not available or restricted due to YouTube's settings."}), 400

    full_text = " ".join([entry['text'] for entry in transcript])

    # Proceed with summarizing the transcript
    try:
        chunk_summaries = [summarize_text(chunk) for chunk in split_text(full_text, max_words=500, overlap=50)]
        combined_summary = " ".join(filter(None, chunk_summaries))
        return jsonify({"summary": combined_summary})
    except Exception as e:
        print(f"Summarization error: {e}")
        return jsonify({"error": "Could not summarize transcript"}), 500

def extract_video_id(youtube_url):
    if "youtu.be" in youtube_url:
        video_id = youtube_url.split('/')[-1].split('?')[0]  # Removes any query params
    elif "youtube.com/watch?v=" in youtube_url:
        video_id = youtube_url.split("v=")[-1].split('&')[0]  # Removes any additional params
    elif "youtube.com/embed/" in youtube_url:
        video_id = youtube_url.split('/embed/')[-1].split('?')[0]
    else:
        video_id = None  # Handles cases with invalid URLs or no recognizable format
    print("Extracted Video ID:", video_id)
    return video_id
    
# Route to test YouTube access
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

# Route to get video metadata (title, author, duration)
@app.route('/video_info', methods=['POST'])
def get_video_info():
    data = request.get_json()
    youtube_url = data.get('url')
    
    if not youtube_url:
        return jsonify({"error": "No YouTube URL provided"}), 400

    video_id = extract_video_id(youtube_url)
    print("Extracted Video ID:", video_id)

    if not video_id:
        return jsonify({"error": "Invalid YouTube URL format"}), 400

    url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,contentDetails&id={video_id}&key={YOUTUBE_API_KEY}"

    try:
        response = requests.get(url)
        data = response.json()

        if 'items' not in data or not data['items']:
            return jsonify({"error": "Video not found or unable to retrieve metadata"}), 404

        title = data['items'][0]['snippet']['title']
        author = data['items'][0]['snippet']['channelTitle']
        duration = data['items'][0]['contentDetails']['duration']
        
        # Construct the thumbnail URL using the video ID
        thumbnail_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"

        return jsonify({
            "title": title,
            "author": author,
            "duration": duration,
            "thumbnail_url": thumbnail_url,
            "youtube_link": f"https://www.youtube.com/watch?v={video_id}"
        })
    except Exception as e:
        print(f"Failed to retrieve video information: {e}")
        return jsonify({"error": f"Failed to retrieve video information: {e}"}), 500

if __name__ == '__main__':
    app.run(debug=True)