import streamlit as st
import newspaper
import nltk
from lxml_html_clean import Cleaner

# Download the necessary punkt tokenizer data for NLP tasks.
nltk.download('punkt')

# Uncommented line for styling Streamlit UI (currently commented out).
# st.markdown('<style> .css-1v0mbdj {margin:0 auto; width:50%; </style>', unsafe_allow_html=True)

# Set the title of the Streamlit app.
st.title('Article Summarizer')

# Create a text input box where users can paste the URL of an article.
url = st.text_input('', placeholder='Paste the URL of the article and press Enter')

# If a URL is provided, the summarization process begins.
if url:
    try:
        # Initialize a `newspaper.Article` object with the provided URL.
        article = newspaper.Article(url)

        # Download the content of the article.
        article.download()
        # Parse the article content to extract structured data like text, title, and more.
        article.parse()

        # Extract and display the main image from the article.
        img = article.top_image
        st.image(img)

        # Extract and display the title of the article.
        title = article.title
        st.subheader(title)

        # Extract and display the authors of the article.
        authors = article.authors
        st.text(','.join(authors))

        # Apply NLP preprocessing to extract additional metadata (like summary and keywords).
        article.nlp()

        # Extract and display keywords from the article.
        keywords = article.keywords
        st.subheader('Keywords:')
        st.write(', '.join(keywords))

        # Create two tabs: one for the full text of the article, and one for the summary.
        tab1, tab2 = st.tabs(["Full Text", "Summary"])
        
        with tab1:
            # Extract and display the full text of the article, removing advertisements.
            txt = article.text
            txt = txt.replace('Advertisement', '')  # Remove unwanted words.
            st.write(txt)
        
        with tab2:
            # Extract and display the summary of the article, removing advertisements.
            st.subheader('Summary')
            summary = article.summary
            summary = summary.replace('Advertisement', '')  # Remove unwanted words.
            st.write(summary)
    
    # Handle any errors that occur during the process and display a message.
    except:
        st.error('Sorry something went wrong')