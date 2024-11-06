from flask import Flask, request, jsonify, render_template
from youtube_transcript_api import YouTubeTranscriptApi
import requests
import os
from youtube_transcript_api._errors import TranscriptNotFound, NoTranscriptAvailable

app = Flask(__name__)

# Hugging Face API settings
API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
headers = {"Authorization": f"Bearer {os.getenv('HUGGING_FACE_API_KEY')}"}

# YouTube Data API Key from environment variable
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')

# Function to summarize text
def summarize_text(text):
    response = requests.post(API_URL, headers=headers, json={"inputs": text})
    if response.status_code == 200:
        return response.json()[0]['summary_text']
    else:
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

# Route to summarize YouTube video transcript
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
    except TranscriptNotFound:
        return jsonify({"error": "Transcript not available due to YouTube restrictions."}), 400
    except NoTranscriptAvailable:
        return jsonify({"error": "No captions available for this video."}), 400
    except Exception as e:
        return jsonify({"error": "An error occurred retrieving the transcript."}), 500

    try:
        chunk_summaries = [summarize_text(chunk) for chunk in split_text(full_text, max_words=500, overlap=50)]
        combined_summary = " ".join(filter(None, chunk_summaries))
        return jsonify({"summary": combined_summary})
    except Exception as e:
        return jsonify({"error": "Could not summarize transcript"}), 500

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

    video_id = youtube_url.split("v=")[-1]
    url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,contentDetails&id={video_id}&key={YOUTUBE_API_KEY}"

    try:
        response = requests.get(url)
        data = response.json()

        if 'items' not in data or not data['items']:
            return jsonify({"error": "Video not found or unable to retrieve metadata"}), 404

        title = data['items'][0]['snippet']['title']
        author = data['items'][0]['snippet']['channelTitle']
        duration = data['items'][0]['contentDetails']['duration']

        return jsonify({
            "title": title,
            "author": author,
            "duration": duration
        })
    except Exception as e:
        return jsonify({"error": f"Failed to retrieve video information: {e}"}), 500

if __name__ == '__main__':
    app.run(debug=True)