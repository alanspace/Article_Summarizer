import os
import re
import torch
import logging
from transformers import SpeechT5Processor, SpeechT5ForTextToSpeech, SpeechT5HifiGan
from datasets import load_dataset
import torchaudio
from concurrent.futures import ThreadPoolExecutor

# Set MPS Fallback Environment Variable
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

# Logging configuration
logging.basicConfig(level=logging.INFO, filename="text_to_audio_mps.log", filemode="w",
                    format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Directory for output audio files
output_dir = "audio_reports_mps"
os.makedirs(output_dir, exist_ok=True)

# Initialize SpeechT5 Model and Processor
def initialize_tts_model():
    """Initialize TTS model with CPU/MPS support."""
    logger.info("Initializing TTS model...")
    device = torch.device("cpu")
    processor = SpeechT5Processor.from_pretrained("./speecht5_tts")
    model = SpeechT5ForTextToSpeech.from_pretrained("./speecht5_tts").to(device)
    vocoder = SpeechT5HifiGan.from_pretrained("./speecht5_hifigan").to(device)
    
    # Load speaker embeddings
    embeddings_dataset = load_dataset("Matthijs/cmu-arctic-xvectors", split="validation")
    speaker_embeddings = torch.tensor(embeddings_dataset[0]["xvector"]).unsqueeze(0).to(device)
    
    logger.info("TTS model initialized.")
    return processor, model, vocoder, speaker_embeddings, device

processor, model, vocoder, speaker_embeddings, device = initialize_tts_model()

def clean_content(content):
    """Clean up the content by removing unnecessary parts like 'Ad Choices'."""
    return re.sub(r"Ad Choices.*", "", content, flags=re.IGNORECASE).strip()

def sanitize_filename(title):
    """Sanitize the title to make it safe for file names."""
    return re.sub(r'[^\w\s-]', '', title).replace(" ", "_")[:50]

def read_articles_from_file(filename):
    """Read and parse articles from the text file."""
    articles = []
    try:
        with open(filename, "r") as file:
            article = {}
            for line in file:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("Source:"):
                    if article:
                        articles.append(article)
                    article = {"source": line.split(":")[1].strip()}
                elif line.startswith("Category:"):
                    article["category"] = line.split(":")[1].strip()
                elif line.startswith("Title:"):
                    article["title"] = line.split(":")[1].strip()
                elif line.startswith("URL:"):
                    article["url"] = line.split(":")[1].strip()
                elif line.startswith("Content:"):
                    article["content"] = line[len("Content:"):].strip()
                elif line.startswith("-" * 80):  # Article separator
                    if article:
                        articles.append(article)
                        article = {}
            if article:  # Add the last article
                articles.append(article)
    except Exception as e:
        logger.error(f"Error reading articles from file: {e}")
    return articles

def text_to_audio(content, filename, batch_size=128):
    """Convert text to audio using Hugging Face SpeechT5 with batch processing."""
    try:
        logger.info(f"Generating audio for {filename}...")

        # Split the text content into smaller batches
        sentences = content.split(". ")
        batched_sentences = [
            ". ".join(sentences[i:i + batch_size]) 
            for i in range(0, len(sentences), batch_size)
        ]

        all_speech = []

        for batch in batched_sentences:
            # Process each batch
            inputs = processor(text=batch, return_tensors="pt").to(device)
            batch_speech = model.generate_speech(
                inputs["input_ids"],
                vocoder=vocoder,
                speaker_embeddings=speaker_embeddings  # Pass speaker embeddings
            )
            all_speech.append(batch_speech)

        # Concatenate all batches into a single tensor
        concatenated_speech = torch.cat(all_speech, dim=-1)

        # Ensure the tensor is 2D for saving (1 channel, samples)
        speech_tensor = concatenated_speech.unsqueeze(0)

        # Save the audio file
        torchaudio.save(filename, speech_tensor.cpu(), sample_rate=16000)
        logger.info(f"Audio saved to {filename}")
    except Exception as e:
        logger.error(f"Error generating audio for {filename}: {e}")

def generate_audio_for_article(article):
    """Generate audio for a single article."""
    try:
        if not article.get("content") or article["content"] in ["[Removed]", "Coming soon."]:
            logger.info(f"Skipped article with missing content: {article.get('title', 'Untitled')}")
            return

        content = clean_content(article["content"])
        if not content or len(content) < 100:
            logger.info(f"Skipped article with insufficient content: {article.get('title', 'Untitled')}")
            return

        text = (
            f"Category: {article.get('category', 'Unknown')}\n"
            f"Source: {article.get('source', 'Unknown')}\n"
            f"Title: {article.get('title', 'No Title')}\n\n"
            f"Content: {content}\n\n"
            f"Source URL: {article.get('url', 'No URL')}\n"
        )
        
        category = article.get("category", "General").replace(" ", "_")
        title = sanitize_filename(article.get("title", "Untitled"))
        audio_filename = os.path.join(output_dir, f"{category}_{title}.wav")
        
        text_to_audio(text, audio_filename)
    except Exception as e:
        logger.error(f"Error processing article {article.get('title', 'Untitled')}: {e}")

def generate_audio_reports(filename):
    """Generate audio reports from a text file."""
    articles = read_articles_from_file(filename)
    with ThreadPoolExecutor(max_workers=12) as executor:  # Utilize CPU cores for parallel processing
        executor.map(generate_audio_for_article, articles)

# Example usage
if __name__ == "__main__":
    api_articles_file = "example_articles.txt"

    print("Generating audio reports...")
    generate_audio_reports(api_articles_file)
    print("Audio reports generated and saved to:", output_dir)