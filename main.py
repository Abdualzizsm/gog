import os
from fastapi import FastAPI, Request, Form, HTTPException, Depends, status, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import os
import json
from datetime import timedelta

from analysis import extract_data_id, get_reviews_from_serpapi, analyze_reviews_with_gemini, get_ratings_distribution
from auth import (
    verify_password, get_password_hash, create_access_token, get_current_user,
    get_users, save_user
)

load_dotenv()

app = FastAPI()

# --- Setup ---
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- Environment Variables & Security ---
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD") # For admin login
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# --- Authentication Endpoints ---

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/token")
async def login_for_access_token(response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    users = get_users()
    user = users.get(form_data.username)
    if not user or not verify_password(form_data.password, user):
        return templates.TemplateResponse("login.html", {
            "request": {},
            "error": "Incorrect username or password"
        }, status_code=400)

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": form_data.username}, expires_delta=access_token_expires
    )
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
    return response

@app.get("/logout", response_class=HTMLResponse)
async def logout(response: Response):
    response = RedirectResponse(url="/login")
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="admin_session")
    return response

# --- Admin Endpoints ---

@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request})

@app.post("/admin/login")
async def handle_admin_login(request: Request, password: str = Form(...)):
    if password == ADMIN_PASSWORD:
        response = RedirectResponse(url="/admin/dashboard", status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="admin_session", value="true", httponly=True)
        return response
    return templates.TemplateResponse("admin_login.html", {"request": request, "error": "Incorrect password"})

def get_admin_session(request: Request):
    if request.cookies.get("admin_session") != "true":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
    return True

@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, _=Depends(get_admin_session)):
    users = get_users()
    return templates.TemplateResponse("admin_dashboard.html", {"request": request, "users": users.keys()})

@app.post("/admin/add_user")
async def add_user(request: Request, username: str = Form(...), password: str = Form(...), _=Depends(get_admin_session)):
    users = get_users()
    if username in users:
        return templates.TemplateResponse("admin_dashboard.html", {
            "request": request, 
            "users": users.keys(),
            "message": f"User '{username}' already exists."
        })
    
    hashed_password = get_password_hash(password)
    save_user(username, hashed_password)
    users = get_users() # Refresh users
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request, 
        "users": users.keys(),
        "message": f"User '{username}' added successfully."
    })

# --- Main Application Endpoints (Protected) ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, user: dict = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.post("/analyze", response_class=HTMLResponse)
async def analyze_reviews(request: Request, map_url: str = Form(...), user: dict = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    if not SERPAPI_API_KEY or not GEMINI_API_KEY:
        return templates.TemplateResponse("index.html", {
            "request": request, "user": user,
            "error": "API keys for SerpApi or Gemini are not configured."
        })

    try:
        data_id = extract_data_id(map_url)
        if not data_id:
            raise ValueError("Could not extract a valid ID from the Google Maps URL.")

        reviews = get_reviews_from_serpapi(data_id)
        if not reviews:
            return templates.TemplateResponse("report.html", {
                "request": request, "user": user,
                "map_url": map_url,
                "error": "No reviews found or failed to fetch reviews for this location."
            })

        analysis_result = analyze_reviews_with_gemini(reviews)
        ratings_distribution = get_ratings_distribution(reviews)

        analysis_result['ratings_distribution'] = ratings_distribution
        analysis_result['review_count'] = len(reviews)

        return templates.TemplateResponse("report.html", {
            "request": request, "user": user,
            "map_url": map_url,
            "report": analysis_result,
            "report_json": json.dumps(analysis_result) # For JS
        })
    except Exception as e:
        return templates.TemplateResponse("index.html", {
            "request": request, "user": user,
            "error": f"An error occurred: {str(e)}"
        })


# To run the app, use the command: uvicorn main:app --reload
