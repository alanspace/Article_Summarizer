from flask import Flask, request, jsonify, render_template
from youtube_transcript_api import YouTubeTranscriptApi
import requests

app = Flask(__name__)

API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"
headers = {"Authorization": "Bearer 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"}  # Replace with your key

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
    return render_template('index.html')

@app.route('/summarize', methods=['POST'])
def summarize_youtube_video():
    data = request.get_json()
    youtube_url = data.get('url')
    video_id = youtube_url.split("v=")[-1]
    
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        full_text = " ".join([entry['text'] for entry in transcript])
    except Exception as e:
        # Handle error if transcript retrieval fails
        return jsonify({"error": "Could not retrieve transcript"}), 400

    # Summarize the transcript if available
    chunk_summaries = [summarize_text(chunk) for chunk in split_text(full_text, max_words=500, overlap=50)]
    combined_summary = " ".join(filter(None, chunk_summaries))
    return jsonify({"summary": combined_summary})

if __name__ == '__main__':
    app.run(debug=True)