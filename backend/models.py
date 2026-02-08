from typing import List, Optional
from pydantic import BaseModel

class Contact(BaseModel):
    name: str
    email: str
    phone: str
    location: str
    linkedin: str
    github: str
    website: Optional[str] = None

class WorkExperience(BaseModel):
    company: str
    role: str
    location: str
    dates: str
    achievements: List[str]

class TechnicalProject(BaseModel):
    title: str
    tech_stack: List[str]
    highlights: List[str]
    category: Optional[str] = None

class Education(BaseModel):
    institution: str
    degree: str
    dates: str
    gpa: str
    honors: Optional[List[str]] = None

class HonorAward(BaseModel):
    award: str
    project: str
    description: str

class Skills(BaseModel):
    languages: List[str]
    frameworks: List[str]
    cloud_tools: List[str]

class MasterProfile(BaseModel):
    contact: Contact
    education: List[Education]
    work_experience: List[WorkExperience]
    technical_projects: List[TechnicalProject]
    honors_and_awards: List[HonorAward]
    skills: Skills
