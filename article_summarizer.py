import streamlit as st
import requests
from bs4 import BeautifulSoup
import urllib.parse
import time
from transformers import pipeline
import torch

# Initialize the summarizer on MPS (GPU)
def initialize_summarizer():
    device = torch.device("mps")  # Use MPS for GPU acceleration
    summarizer = pipeline("summarization", model="facebook/bart-large-cnn", device=0)  # `device=0` enables MPS
    return summarizer

# Initialize summarizer globally
summarizer = initialize_summarizer()

# Function to measure runtime
def summarize_with_timing(text):
    start_time = time.time()
    result = summarizer(text, max_length=130, min_length=30, do_sample=False)
    end_time = time.time()
    runtime = end_time - start_time
    print(f"Summary runtime on MPS: {runtime:.2f} seconds")
    return result[0]["summary_text"], runtime

# Streamlit app
st.title('Article Summarizer')

url = st.text_input('Article URL', placeholder='Paste the URL of the article and press Enter', label_visibility='collapsed')

if url:
    try:
        # Fetch article
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract main image
        img_tag = soup.find('img')
        if img_tag and img_tag.get('src'):
            img_url = urllib.parse.urljoin(url, img_tag['src'])
            st.image(img_url)

        # Extract title
        title = soup.title.string if soup.title else 'No Title Found'
        st.subheader(title)

        # Extract content
        paragraphs = soup.find_all('p')
        full_text = " ".join(p.get_text() for p in paragraphs)

        # Display content
        tab1, tab2 = st.tabs(["Full Text", "Summary"])
        with tab1:
            st.write(full_text or 'No content available.')
        with tab2:
            st.subheader('Summary')
            # Summarize and measure runtime
            summary, runtime = summarize_with_timing(full_text)
            st.write(summary or 'No summary available.')
            st.info(f"Summary generated in {runtime:.2f} seconds.")

    except Exception as e:
        st.error(f'Sorry something went wrong: {e}')