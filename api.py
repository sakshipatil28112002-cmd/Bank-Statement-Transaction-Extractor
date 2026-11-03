from fastapi import FastAPI

from api_routes import profile_routes, transaction_routes
from database import create_tables


# Create FastAPI application
app = FastAPI(
    title="Bank Statement Extractor API",
    description="API for extracting bank statements from PDF files and storing them in a database.",
    version="1.0.0"
)


# Create database tables when API starts
@app.on_event("startup")
def startup():
    create_tables()


# Register Profile and Transaction routes
app.include_router(profile_routes.router)
app.include_router(transaction_routes.router)


# Home endpoint
@app.get("/")
def home():
    return {
        "message": "Bank Statement Extractor API is running"
    }


# Health endpoint
@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }