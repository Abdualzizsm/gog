import os
import re
import json
import requests
import google.generativeai as genai
from serpapi import GoogleSearch
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- API Configuration ---
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("Gemini API key not found. Please set it in the .env file.")
genai.configure(api_key=GEMINI_API_KEY)

# --- Helper Functions ---

def get_redirected_url(url: str) -> str:
    """Follows a shortened URL (like maps.app.goo.gl) to its final destination."""
    try:
        response = requests.head(url, allow_redirects=True, timeout=10)
        return response.url
    except requests.RequestException as e:
        print(f"Error fetching redirected URL: {e}")
        return url # Return original url if redirect fails

def extract_data_id(url: str) -> str | None:
    """Extracts the Google Maps data ID from a URL."""
    if "maps.app.goo.gl" in url:
        url = get_redirected_url(url)

    # Regex to find the data ID (starts with 0x)
    match = re.search(r'1s(0x[a-f0-9]+:0x[a-f0-9]+)!', url)
    if match:
        return match.group(1)
    return None

# --- Core Functions ---

def get_reviews_from_serpapi(data_id: str, max_pages: int = 2) -> list:
    """Fetches reviews for a given data_id using the SerpApi Google Maps Reviews API."""
    if not SERPAPI_API_KEY:
        raise ValueError("SerpApi API key not found. Please set it in the .env file.")

    all_reviews = []
    params = {
        "engine": "google_maps_reviews",
        "data_id": data_id,
        "api_key": SERPAPI_API_KEY,
        "hl": "ar", # Fetch reviews in Arabic
    }

    search = GoogleSearch(params)
    page_num = 0

    while page_num < max_pages:
        results = search.get_dict()
        if "error" in results:
            raise Exception(f"SerpApi Error: {results['error']}")

        reviews = results.get("reviews", [])
        if not reviews:
            break
        
        all_reviews.extend(reviews)

        # Check for next page
        if "next" in results.get("serpapi_pagination", {}):
            search.params_dict.update(results["serpapi_pagination"])
            page_num += 1
        else:
            break
            
    return all_reviews

def analyze_reviews_with_gemini(reviews: list) -> dict:
    """Analyzes a list of reviews using the Gemini API and returns a structured report."""
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # Prepare the reviews text for the prompt
    reviews_text = "\n".join([f"- {r.get('snippet', 'No content')}" for r in reviews])

    prompt = f"""
    Based on the following customer reviews from Google Maps, please provide a comprehensive analysis in Arabic.

    **Reviews:**
    {reviews_text}

    **Required Analysis (provide the output in a valid JSON format only, with the specified keys):**
    1.  **swot**: A SWOT analysis.
        -   `strengths`: (Array of strings) List 3-5 key strengths.
        -   `weaknesses`: (Array of strings) List 3-5 key weaknesses.
        -   `opportunities`: (Array of strings) List 2-3 potential opportunities.
        -   `threats`: (Array of strings) List 2-3 potential threats.
    2.  **sentiment**: The overall sentiment. Must be one of: 'Positive', 'Negative', 'Neutral'.
    3.  **keywords**: (Array of strings) A list of the 5-7 most common and relevant keywords or phrases.
    4.  **summary**:
        -   `problems`: (Array of strings) A summary of the most common problems mentioned.
        -   `solutions`: (Array of strings) Suggest actionable solutions for the identified problems.
    5.  **classified_reviews**: (Array of objects) Classify each review individually.
        -   `snippet`: (String) The original review text.
        -   `sentiment`: (String) The sentiment of the review ('Positive', 'Negative', 'Neutral').

    **Example JSON output format:**
    {{
        "swot": {{
            "strengths": ["Service is excellent"],
            "weaknesses": ["Prices are high"],
            "opportunities": ["Expand delivery service"],
            "threats": ["New competitor opening nearby"]
        }},
        "sentiment": "Positive",
        "keywords": ["service", "price", "location"],
        "summary": {{
            "problems": ["Customers complain about high prices."],
            "solutions": ["Introduce a value menu."]
        }},
        "classified_reviews": [
            {{ "snippet": "The service was amazing, very fast!", "sentiment": "Positive" }},
            {{ "snippet": "It was okay, nothing special.", "sentiment": "Neutral" }},
            {{ "snippet": "Terrible experience, very rude staff.", "sentiment": "Negative" }}
        ]
    }}
    """

    try:
        response = model.generate_content(prompt)
        # Clean the response to ensure it's valid JSON
        cleaned_response = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(cleaned_response)
    except Exception as e:
        print(f"Error during Gemini analysis: {e}")
        print(f"Gemini raw response: {response.text if 'response' in locals() else 'No response'}")
        raise Exception("Failed to get a valid JSON response from the analysis API.")

def get_ratings_distribution(reviews: list) -> dict:
    """Calculates the distribution of star ratings."""
    distribution = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
    for review in reviews:
        rating = review.get("rating")
        if rating:
            # Ratings are float (e.g., 4.0), convert to int string key
            star = str(int(rating))
            if star in distribution:
                distribution[star] += 1
    return distribution
