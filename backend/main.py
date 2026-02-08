from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import os
from datetime import datetime
from typing import Optional

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Import our modules
from backend.models import MasterProfile
from backend.pdf_generator import PDFGenerator

app = FastAPI(title="AI Career Suite Backend")

# CORS for local extension development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to extension ID
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load Master Profile
PROFILE_PATH = "MasterProfile.json"
try:
    with open(PROFILE_PATH, "r") as f:
        profile_data = json.load(f)
        master_profile = MasterProfile(**profile_data)
except Exception as e:
    print(f"Error loading MasterProfile.json: {e}")
    # Initialize empty or handle error
    master_profile = None

pdf_gen = PDFGenerator()

class ExportRequest(BaseModel):
    content: str
    type: str # 'resume' or 'cover_letter'
    company_name: Optional[str] = None
    date: Optional[str] = None

@app.get("/")
async def root():
    return {"message": "AI Career Suite Backend Running"}

@app.post("/api/v1/export-pdf")
async def export_pdf(request: ExportRequest):
    if not master_profile:
        raise HTTPException(status_code=500, detail="Master profile not loaded")

    try:
        if request.type == 'resume':
            # Generate Resume from Markdown content
            # Content is expected to be Markdown
            pdf_buffer = pdf_gen.generate_resume_from_markdown(request.content, master_profile.dict())
            filename = "Resume.pdf"
        
        elif request.type == 'cover_letter':
            # Generate Cover Letter from Text content
            date_str = request.date or datetime.now().strftime("%B %d, %Y")
            company = request.company_name or "Hiring Team"
            pdf_buffer = pdf_gen.generate_cover_letter(master_profile.dict(), request.content, company, date_str)
            filename = "CoverLetter.pdf"
        
        else:
            raise HTTPException(status_code=400, detail="Invalid export type")

        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

from backend.agents import agent_workflow

@app.post("/api/v1/generate")
async def generate_drafts(job_description: str = Body(..., embed=True)):
    """
    Generates resume and cover letter drafts using the AI Agent.
    """
    if not master_profile:
        raise HTTPException(status_code=500, detail="Master profile not loaded")

    # Invoke the agent
    # We pass the profile and JD to the initial state
    initial_state = {
        "job_description": job_description,
        "profile": master_profile.dict(),
        "resume_markdown": "",
        "cover_letter_text": ""
    }

    try:
        # Run the graph
        result = agent_workflow.invoke(initial_state)
        
        return {
            "resume": result["resume_markdown"],
            "coverLetter": result["cover_letter_text"]
        }
    except Exception as e:
        print(f"Agent generation error: {e}")
        # Build a fallback if LLM fails (e.g. no API key)
        # For now, raise detailed error
        raise HTTPException(status_code=500, detail=str(e))
