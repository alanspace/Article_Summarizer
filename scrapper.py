import os
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import urllib.parse
import logging

# Logging configuration
logging.basicConfig(level=logging.INFO, filename="scraper.log", filemode="w",
                    format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables
env_path = os.path.join(os.getcwd(), "APIkey.env")
env_loaded = load_dotenv(env_path)

# Get API keys
API_KEYS = {
    "newsapi": os.getenv("NEWS_API_KEY"),
    "gnews": os.getenv("GNEWS_API_KEY"),
    "currents": os.getenv("CURRENTS_API_KEY"),
}

# Fetch articles from NewsAPI
def fetch_articles_from_newsapi(query, api_key, limit=5, category="General"):
    try:
        url = f"https://newsapi.org/v2/everything?q={query}&apiKey={api_key}&pageSize={limit}"
        response = requests.get(url)
        response.raise_for_status()
        articles = response.json().get("articles", [])
        return [
            {
                "title": article.get("title", "No Title Found"),
                "image_url": article.get("urlToImage"),
                "content": article.get("content", ""),
                "source": "NewsAPI",
                "url": article.get("url"),
                "category": category,
            }
            for article in articles
        ]
    except Exception as e:
        logger.error(f"Error fetching from NewsAPI: {e}")
        return []

# Fetch articles from GNews
def fetch_articles_from_gnews(query, api_key, limit=5, category="General"):
    try:
        url = f"https://gnews.io/api/v4/search?q={query}&token={api_key}&max={limit}"
        response = requests.get(url)
        response.raise_for_status()
        articles = response.json().get("articles", [])
        return [
            {
                "title": article.get("title", "No Title Found"),
                "image_url": article.get("image"),
                "content": article.get("description", ""),
                "source": "GNews",
                "url": article.get("url"),
                "category": category,
            }
            for article in articles
        ]
    except Exception as e:
        logger.error(f"Error fetching from GNews: {e}")
        return []

# Fetch articles from Currents API
def fetch_articles_from_currents(query, api_key, limit=5, category="General"):
    try:
        url = f"https://api.currentsapi.services/v1/search?keywords={query}&apiKey={api_key}&limit={limit}"
        response = requests.get(url)
        response.raise_for_status()
        articles = response.json().get("news", [])
        return [
            {
                "title": article.get("title", "No Title Found"),
                "image_url": article.get("image"),
                "content": article.get("description", ""),
                "source": "Currents",
                "url": article.get("url"),
                "category": category,
            }
            for article in articles
        ]
    except Exception as e:
        logger.error(f"Error fetching from Currents API: {e}")
        return []

# Fetch article full content
def fetch_article(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        title = soup.title.string.strip() if soup.title else "No Title Found"
        img_tag = soup.find("img")
        img_url = urllib.parse.urljoin(url, img_tag["src"]) if img_tag and img_tag.get("src") else None
        paragraphs = soup.find_all("p")
        full_text = " ".join(p.get_text(strip=True) for p in paragraphs)

        return {
            "title": title,
            "image_url": img_url,
            "content": full_text,
            "source": "Scraped",
            "url": url,
        }
    except Exception as e:
        logger.error(f"Error fetching article: {e}")
        return None

# Deduplicate articles
def deduplicate_articles(articles):
    seen_urls = set()
    unique_articles = []
    for article in articles:
        if article['url'] not in seen_urls:
            unique_articles.append(article)
            seen_urls.add(article['url'])
    return unique_articles

# Fetch and categorize articles
def get_news_articles(categories_queries):
    articles = []
    for category, query in categories_queries.items():
        articles.extend(fetch_articles_from_newsapi(query, API_KEYS["newsapi"], limit=5, category=category))
        articles.extend(fetch_articles_from_gnews(query, API_KEYS["gnews"], limit=5, category=category))
        articles.extend(fetch_articles_from_currents(query, API_KEYS["currents"], limit=5, category=category))
    articles = fetch_full_text_for_articles(articles)
    return deduplicate_articles(articles)

# Fetch full text for articles
def fetch_full_text_for_articles(articles):
    updated_articles = []
    for article in articles:
        if article.get("url") and (not article.get("content") or len(article["content"]) < 300):
            full_article = fetch_article(article["url"])
            if full_article:
                article["content"] = full_article["content"]
        updated_articles.append(article)
    return updated_articles

# Save articles to a text file
def save_articles_to_file(articles, filename="articles.txt"):
    with open(filename, "w") as file:
        for article in articles:
            if not article.get("content") or "[Removed]" in article["content"]:
                continue
            file.write(f"Source: {article.get('source')}\n")
            file.write(f"Category: {article.get('category')}\n")
            file.write(f"Title: {article.get('title')}\n")
            file.write(f"URL: {article.get('url')}\n")
            file.write(f"Image URL: {article.get('image_url')}\n")
            file.write(f"Content: {article.get('content')}\n")
            file.write("-" * 80 + "\n")
    logger.info(f"Articles saved to {filename}")

# Main execution
if __name__ == "__main__":
    api_categories = {
        "Technology": "technology",
        "Science & Health": "science",
        "Artificial Intelligence": "artificial intelligence",
        "AI v the Mind": "AI mind",
    }

    bbc_categories = {
        "Technology": "https://www.bbc.com/innovation/technology",
        "Science & Health": "https://www.bbc.com/innovation/science",
        "Artificial Intelligence": "https://www.bbc.com/innovation/artificial-intelligence",
        "AI v the Mind": "https://www.bbc.com/innovation/ai-v-the-mind",
    }

    logger.info("Fetching articles from APIs...")
    api_articles = get_news_articles(api_categories)
    save_articles_to_file(api_articles, filename="api_articles.txt")

    logger.info("Fetching articles from BBC categories...")
    bbc_articles = []
    for category, url in bbc_categories.items():
        article = fetch_article(url)
        if article:
            article["category"] = category
            bbc_articles.append(article)
    save_articles_to_file(bbc_articles, filename="bbc_articles.txt")