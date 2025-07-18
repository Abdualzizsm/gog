import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from analysis import (
    extract_data_id,
    get_reviews_from_serpapi,
    analyze_reviews_with_gemini,
    get_ratings_distribution
)

# Load environment variables from .env file
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Review Analyzer",
    description="An API to analyze Google Maps reviews using SerpApi and Gemini.",
    version="1.0.0"
)

# Mount static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup templates directory
templates = Jinja2Templates(directory="templates")

# Get API keys from environment variables
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Render the main page of the application."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/analyze", response_class=HTMLResponse)
async def analyze_reviews(request: Request, map_url: str = Form(...)):
    """Analyzes the reviews from a Google Maps URL."""
    try:
        # 1. Extract Data ID from URL
        data_id = extract_data_id(map_url)
        if not data_id:
            raise ValueError("Could not extract a valid Google Maps Place ID from the URL. Please provide a correct link.")

        # 2. Fetch reviews using SerpApi
        reviews = get_reviews_from_serpapi(data_id)
        if not reviews:
            raise ValueError("No reviews found for this location or the location is invalid.")

        # 3. Analyze reviews with Gemini
        analysis_result = analyze_reviews_with_gemini(reviews)

        # 4. Get ratings distribution
        ratings_distribution = get_ratings_distribution(reviews)
        analysis_result['ratings_distribution'] = ratings_distribution

        # 5. Render the report page with the results
        return templates.TemplateResponse("report.html", {
            "request": request,
            "report": analysis_result,
            "map_url": map_url
        })

    except Exception as e:
        # Handle any errors that occur during the process
        print(f"An error occurred: {e}")
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": str(e)
        })


# To run the app, use the command: uvicorn main:app --reload
