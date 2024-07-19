import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import json
from urllib.parse import urljoin
from tqdm import tqdm
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from markdownify import markdownify as md
import logging
from langdetect import detect, LangDetectException
import spacy
import os
import concurrent.futures
from functools import lru_cache
import re
import time

# Configuration
MAX_WORKERS = 20
OUTPUT_DIR = '/app/output'
OUTPUT_FILE = 'english_welsh_pairs.jsonl'

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load spaCy model for English only
nlp_en = spacy.load("en_core_web_sm")

def create_session_with_retries():
    logger.debug("Creating session with retries")
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries, pool_connections=100, pool_maxsize=100)
    session.mount('https://', adapter)
    return session

session = create_session_with_retries()

@lru_cache(maxsize=1000)
def get_urls(sitemap_url):
    logger.debug(f"Fetching URLs from sitemap: {sitemap_url}")
    response = session.get(sitemap_url)
    root = ET.fromstring(response.content)
    urls = [loc.text for loc in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
    logger.debug(f"Found {len(urls)} URLs in sitemap {sitemap_url}")
    return urls

def get_language_switch_url(soup, current_url):
    switch_link = soup.find('a', class_='language-link', string='Cymraeg')
    if switch_link and 'href' in switch_link.attrs:
        welsh_url = urljoin(current_url, switch_link['href'])
        logger.debug(f"Found Welsh URL {welsh_url} for English URL {current_url}")
        return welsh_url
    logger.debug(f"No Welsh URL found for English URL {current_url}")
    return None

def find_language_pair(url):
    logger.debug(f"Finding language pair for URL: {url}")
    try:
        response = session.get(url)
        soup = BeautifulSoup(response.content, 'lxml')
        welsh_url = get_language_switch_url(soup, url)
        if welsh_url:
            logger.info(f"Found language pair: {url} (EN) - {welsh_url} (CY)")
            return (url, welsh_url)
    except Exception as e:
        logger.error(f"Error processing {url}: {str(e)}")
    return None

def get_announcement_articles(soup):
    articles = [md(str(article), strip=['a']) for article in soup.find_all('div', class_='announcement-item__article')]
    logger.debug(f"Found {len(articles)} articles")
    return articles

def scrape_page(url):
    logger.debug(f"Scraping page: {url}")
    try:
        time.sleep(REQUEST_DELAY)  # Add delay between requests
        response = session.get(url)
        soup = BeautifulSoup(response.content, 'lxml')
        articles = get_announcement_articles(soup)
        return articles
    except Exception as e:
        logger.error(f"Error scraping {url}: {str(e)}")
        return []

@lru_cache(maxsize=1000)
def extract_probable_entities(text):
    words = text.split()
    return {word.lower() for word in words if word[0].isupper() and len(word) > 1}

def quality_check(en_text, cy_text):
    logger.debug("Performing quality check")
    en_length, cy_length = len(en_text.split()), len(cy_text.split())
    length_ratio = min(en_length, cy_length) / max(en_length, cy_length)
    
    # Accept very short texts if they have similar lengths
    if en_length < 10 and cy_length < 10 and length_ratio > 0.5:
        logger.debug("Passed: Short text with similar lengths")
        return True
    
    # For longer texts, be more lenient
    if length_ratio < 0.2:
        logger.debug("Failed: Length ratio too small")
        return False

    # 2. Common word check
    common_en_words = set('the and of to in is for on that by a are you we with as at from have'.split())
    common_cy_words = set('y a i yn o ar mae am gyda bod gan ei yr yng chi yw'.split())
    
    en_words = set(en_text.lower().split())
    cy_words = set(cy_text.lower().split())
    
    en_common_count = len(en_words.intersection(common_en_words))
    cy_common_count = len(cy_words.intersection(common_cy_words))
    
    if en_common_count == 0 or cy_common_count == 0:  # Extremely relaxed condition
        return False

    # 3. Language detection confirmation (made optional)
    try:
        en_detected = detect(en_text)
        cy_detected = detect(cy_text)
        if en_detected != 'en' and cy_detected != 'cy':
            return False
    except LangDetectException:
        # If language detection fails, we'll still consider it potentially valid
        pass

    # 4. Named entity and number comparison
    en_entities = extract_probable_entities(en_text)
    cy_entities = extract_probable_entities(cy_text)
    
    en_numbers = set(re.findall(r'\d+', en_text))
    cy_numbers = set(re.findall(r'\d+', cy_text))
    
    common_elements = en_entities.intersection(cy_entities).union(en_numbers.intersection(cy_numbers))
    
    if len(common_elements) > 0:
        return True

    # 5. Check for similar sentence structure
    en_sentence_count = len(re.findall(r'[.!?]+', en_text))
    cy_sentence_count = len(re.findall(r'[.!?]+', cy_text))
    if abs(en_sentence_count - cy_sentence_count) <= 1:
        return True

    # 6. Check for similar paragraph structure
    en_paragraph_count = len(en_text.split('\n\n'))
    cy_paragraph_count = len(cy_text.split('\n\n'))
    if en_paragraph_count == cy_paragraph_count:
        return True

    logger.debug("Failed: No passing conditions met")
    return False

def process_url_pair(en_url, cy_url):
    logger.info(f"Processing URL pair: {en_url} (EN) - {cy_url} (CY)")
    en_articles = scrape_page(en_url)
    cy_articles = scrape_page(cy_url)

    valid_pairs = []
    for i, (en, cy) in enumerate(zip(en_articles, cy_articles)):
        if quality_check(en, cy):
            valid_pairs.append((en, cy, en_url))
            logger.debug(f"Valid pair found for article {i+1} from {en_url}")
        else:
            logger.debug(f"Pair failed quality check for article {i+1} from {en_url}: {en[:50]}... | {cy[:50]}...")
    logger.info(f"Found {len(valid_pairs)} valid pairs out of {len(en_articles)} total pairs for {en_url}")
    return valid_pairs

def main():
    try:
        logger.info("Starting web scraping process")
        root_sitemap = "https://www.gov.wales/sitemap.xml"
        sitemap_urls = get_urls(root_sitemap)
        logger.info(f"Found {len(sitemap_urls)} sitemaps")

        all_page_urls = []
        for sitemap_url in tqdm(sitemap_urls, desc="Fetching sitemaps"):
            urls = get_urls(sitemap_url)
            all_page_urls.extend(urls)
            logger.debug(f"Added {len(urls)} URLs from sitemap {sitemap_url}")

        logger.info(f"Total pages found: {len(all_page_urls)}")

        # Phase 1: Collect English-Welsh URL pairs
        logger.info("Phase 1: Collecting English-Welsh URL pairs")
        url_pairs = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {executor.submit(find_language_pair, url): url for url in all_page_urls}
            for future in tqdm(concurrent.futures.as_completed(future_to_url), total=len(all_page_urls), desc="Finding language pairs"):
                pair = future.result()
                if pair:
                    url_pairs.append(pair)

        logger.info(f"Found {len(url_pairs)} English-Welsh URL pairs")

        # Phase 2: Scrape content from URL pairs
        logger.info("Phase 2: Scraping content from URL pairs")
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        total_pairs = 0
        valid_pairs = 0
        with open(os.path.join(OUTPUT_DIR, OUTPUT_FILE), 'w', encoding='utf-8') as f:
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                future_to_pair = {executor.submit(process_url_pair, en_url, cy_url): (en_url, cy_url) for en_url, cy_url in url_pairs}
                for future in tqdm(concurrent.futures.as_completed(future_to_pair), total=len(url_pairs), desc="Scraping pages"):
                    results = future.result()
                    total_pairs += len(results)
                    for en, cy, url in results:
                        json.dump({"en": en, "cy": cy, "url": url}, f, ensure_ascii=False)
                        f.write('\n')
                        valid_pairs += 1
                        logger.debug(f"Wrote valid pair to output file: {url}")

        logger.info(f"Scraping complete. Found {valid_pairs} valid pairs out of {total_pairs} total pairs.")
        logger.info(f"Data stored in {os.path.join(OUTPUT_DIR, OUTPUT_FILE)}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")

if __name__ == "__main__":
    main()