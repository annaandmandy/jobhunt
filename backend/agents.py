import os
import json
from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# Define State
class AgentState(TypedDict):
    job_description: str
    profile: dict
    resume_markdown: str
    cover_letter_text: str

# Initialize LLM (Ensure OPENAI_API_KEY is found in env)
# For demo purposes, we assume it's set or will be set.
llm = ChatOpenAI(model="gpt-4o")

# --- Prompts ---

RESUME_PROMPT = """
You are an expert technical resume writer. 
Your goal is to tailor the user's Master Profile to the given Job Description.
Produce a clean, ATS-friendly Markdown resume that fits on ONE PAGE.

**Guidelines:**
1.  **Structure:**
    *   **Do NOT include header or contact info.** Header is provided elsewhere.
    *   **Summary (1 line):** Role focus + specialization.
    *   **Education:** Degree, University, Dates, GPA (opt).
    *   **Work Experience:** Professional roles (e.g., Internships, Full-time). Focus on scale, infrastructure, and impact.
    *   **Technical Projects:** Personal or academic projects. Focus on initiative, agentic workflows, and complex architecture.
    *   **Skills:** Languages, Frameworks, Cloud/Tools.
    *   **Honors & Awards:** (If relevant).

2.  **Content Tailoring:**
    *   Highlight skills and experiences from the profile that match the Job Description.
    *   Rephrase bullet points to emphasize impact and relevance to the JD keywords.
    *   Do NOT invent facts. Only use data from the Master Profile.
    *   Ensure distinct separation between "Work Experience" and "Technical Projects".

3.  **Format (tight, one-page):**
    *   Use Markdown headers (## for Sections, ### for Roles/Titles).
    *   Use bullet points for achievements.
    *   Limit bullets: max 3 per role, max 2 per project.
    *   Keep bullets short (1 line each, ~18 words).
    *   Use compact spacing; no blank lines between bullets.
    *   Keep it to ONE PAGE length (be concise).

**Job Description:**
{job_description}

**Master Profile:**
{profile_json}

**Output:**
Return ONLY the Markdown content of the new resume.
"""

COVER_LETTER_PROMPT = """
You are a professional career coach. Write a compelling, concise cover letter for the user based on their profile and the job description.
Match this tone: clear, direct, human, and warm (not overly formal).

**Guidelines:**
1.  **Style:** Professional, enthusiastic, but not robotic.
2.  **Structure:**
    *   Do NOT include header/contact info. Header is provided elsewhere.
    *   Short salutation (use "Hello," unless a specific name is provided).
    *   **Hook:** State interest in the role and company specifically.
    *   **Body Paragraph 1 (Experience):** Connect specific requirements in the JD to the user's Work Experience (e.g., Finz, BU BIT Lab).
    *   **Body Paragraph 2 (Projects):** Connect "Technical Projects" (e.g., Multi-agent Novel Gen) to the role's needs (especially if AI/Agentic role). Uses specific tech stack details.
    *   **Closing:** Reiterate value and interest. sign-off.
3.  **Connecting the dots:** explicitly link the user's past achievements to the company's problems/stack mentioned in the JD.
4.  **Length:** ONE PAGE; 3 short paragraphs max, 4-6 sentences total.

**Job Description:**
{job_description}

**Master Profile:**
{profile_json}

**Output:**
Return ONLY the text of the cover letter (plain text with paragraphs).
"""

# --- Nodes ---

def tailor_resume(state: AgentState):
    print("--- TAILORING RESUME ---")
    prompt = ChatPromptTemplate.from_template(RESUME_PROMPT)
    chain = prompt | llm
    
    response = chain.invoke({
        "job_description": state["job_description"],
        "profile_json": json.dumps(state["profile"], indent=2)
    })
    
    return {"resume_markdown": response.content}

def write_cover_letter(state: AgentState):
    print("--- WRITING COVER LETTER ---")
    prompt = ChatPromptTemplate.from_template(COVER_LETTER_PROMPT)
    chain = prompt | llm
    
    response = chain.invoke({
        "job_description": state["job_description"],
        "profile_json": json.dumps(state["profile"], indent=2)
    })
    
    return {"cover_letter_text": response.content}

# --- Graph Construction ---

workflow = StateGraph(AgentState)

workflow.add_node("tailor_resume", tailor_resume)
workflow.add_node("write_cover_letter", write_cover_letter)

# Run in parallel
workflow.set_entry_point("tailor_resume")
workflow.set_entry_point("write_cover_letter") 
# Wait, StateGraph entry point must be single or conditional? 
# To run in parallel, we can have a start node that branches?
# LangGraph allows multiple entry points? Or we just chain them?
# Let's chain them for simplicity or use a parallel map pattern.
# Actually, they are independent. We can use a fork.

# Redefine graph for parallel execution
workflow = StateGraph(AgentState)
workflow.add_node("tailor_resume", tailor_resume)
workflow.add_node("write_cover_letter", write_cover_letter)

# Since they update disjoint keys in the state, parallel is safe.
# Start -> (Resume, Cover) -> End
# In LangGraph, we can't easily express strictly parallel start without a common start node or routing.
# But we can just chain them sequentially since they don't depend on each other's output (only input).
# Sequential is fine and easier to debug.

workflow.set_entry_point("tailor_resume")
workflow.add_edge("tailor_resume", "write_cover_letter")
workflow.add_edge("write_cover_letter", END)

agent_workflow = workflow.compile()
