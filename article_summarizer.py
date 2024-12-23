import streamlit as st
from scraper import fetch_article  # Import the scraper
from transformers import pipeline
import torch
import time

def initialize_summarizer():
    """Initialize the summarizer pipeline."""
    if torch.cuda.is_available():
        device = 0
    elif torch.backends.mps.is_available():
        device = 0
    else:
        device = -1
    return pipeline("summarization", model="sshleifer/distilbart-cnn-12-6", device=device)

def summarize_with_timing(text, summarizer, max_length=250, min_length=100):
    summaries = []
    runtime = 0
    for i in range(0, len(text.split()), 512):
        chunk = " ".join(text.split()[i:i+512])
        start_time = time.time()
        result = summarizer(chunk, max_length=max_length, min_length=min_length, do_sample=False)
        runtime += time.time() - start_time
        summaries.append(result[0]["summary_text"])
    return " ".join(summaries), runtime

# Streamlit App
st.title("Article Summarizer")
summarizer = initialize_summarizer()

url = st.text_input("Enter the article URL:")
if url:
    with st.spinner("Fetching and summarizing the article..."):
        article = fetch_article(url)  # Use the scraper
        if article and article.get("content"):
            st.image(article.get("image_url"))
            st.subheader(article.get("title"))
            st.write(article.get("content"))

            summary, runtime = summarize_with_timing(article["content"], summarizer, max_length=300, min_length=150)
            st.write("### Summary")
            st.write(summary)
            st.info(f"Summary generated in {runtime:.2f} seconds.")
        else:
            st.error("Could not fetch or summarize the article.")