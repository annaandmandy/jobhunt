import json
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

# Define State
class AgentState(TypedDict, total=False):
    job_description: str
    profile: dict
    target_persona: dict
    requirement_map: dict
    reviewer_instructions: str
    match_score: int
    critique: dict
    review_rounds: int
    best_resume_markdown: str
    best_cover_letter_text: str
    best_match_score: int
    resume_markdown: str
    cover_letter_text: str

# Initialize LLM (Ensure OPENAI_API_KEY is found in env)
# For demo purposes, we assume it's set or will be set.
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")

def _safe_json_loads(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    if "{" in cleaned and "}" in cleaned:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        cleaned = cleaned[start:end + 1]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"raw": text}

# --- Prompts ---

JD_STRATEGIST_PROMPT = """
You are The JD Strategist (The Analyzer). Read the job description and infer the hidden requirements.

**Tasks:**
1) Determine the target persona the company wants (e.g., "Scrappy Startup Generalist", "Scale-focused Backend Expert").
2) Extract hard skills and soft skills.
3) Identify the core problem the role is meant to solve.
4) Capture key keywords and signals for ATS.

**Job Description:**
{job_description}

**Output (JSON only):**
{{
  "persona": "",
  "hard_skills": [],
  "soft_skills": [],
  "core_problem": "",
  "keywords": []
}}
"""

EXPERIENCE_MATCHER_PROMPT = """
You are The Experience Matcher (The Mapper). Map job requirements to the strongest evidence from the Master Profile.

**Rules:**
- Be concise. Return only the information that should be used in writing.
- Limit to 5-7 total requirements, highest impact only.
- For each requirement, provide at most 2 evidence items.
- Keep each evidence detail to one short sentence (<= 20 words).
- Prioritize the most relevant 2-4 projects and 2-4 experience entries.
- Use only facts from the Master Profile.

**Job Description:**
{job_description}

**Target Persona:**
{target_persona_json}

**Master Profile:**
{profile_json}

**Output (JSON only):**
{{
  "requirement_map": [
    {{
      "requirement": "",
      "evidence": [
        {{
          "source": "experience|project|education",
          "title": "",
          "detail": ""
        }}
      ]
    }}
  ],
  "focus_projects": [],
  "focus_experience": []
}}
"""

GHOSTWRITER_RESUME_PROMPT = """
You are an expert technical resume writer. 
Your goal is to tailor the user's Master Profile to the given Job Description.
Produce a clean, ATS-friendly Markdown resume that fits on ONE PAGE.

**Guidelines:**
1.  **Structure:**
    *   **Do NOT include header or contact info.** Header is provided elsewhere.
    *   **Summary (2 line):** Role focus + specialization.
    *   **Education:** Degree, University, Dates, GPA (opt).
    *   **Work Experience:** Include ALL roles from the Master Profile. Focus on scale, infrastructure, and impact.
    *   **Technical Projects:** Personal or academic projects. Focus on initiative, agentic workflows, and complex architecture.
    *   **Skills:** Languages, Frameworks, Cloud/Tools.
    *   **Honors & Awards:** (If relevant).

2.  **Content Tailoring:**
    *   Highlight skills and experiences from the profile that match the Job Description.
    *   Rephrase bullet points to emphasize impact and relevance to the JD keywords.
    *   Use the Requirement Map to prioritize which experiences/projects become bullet points.
    *   Each bullet should reflect a JD requirement or keyword where possible.
    *   If the Reviewer Instructions call out missing skills, add them to Skills and weave into relevant bullets **only if they exist in the Master Profile** (including coursework or minor exposure).
    *   Do NOT invent facts. Only use data from the Master Profile.
    *   Ensure distinct separation between "Work Experience" and "Technical Projects".

3.  **Format (tight, one-page):**
    *   Use Markdown headers (## for Sections, ### for Roles/Titles).
    *   Use "-" for bullet points.
    *   Insert a blank line between any date line and the bullet list.
    *   Limit bullets: max 3 per role, max 2 per project.
    *   Keep bullets short (1 line each, ~18 words).
    *   Use compact spacing; no blank lines between bullets.
    *   Keep it to ONE PAGE length (be concise).

**Job Description:**
{job_description}

**Target Persona:**
{target_persona_json}

**Requirement Map:**
{requirement_map_json}

**Reviewer Instructions (if any):**
{reviewer_instructions}

**Master Profile:**
{profile_json}

**Output:**
Return ONLY the Markdown content of the new resume.
Do NOT wrap the output in code fences.
"""

GHOSTWRITER_COVER_LETTER_PROMPT = """
You are a professional career coach. Write a compelling, concise cover letter for the user based on their profile and the job description.
Match this tone: clear, direct, human, and warm (not overly formal).

**Guidelines:**
1.  **Style:** Professional, enthusiastic, but not robotic.
2.  **Structure:**
    *   Do NOT include header/contact info and Sincerely part. Header and signiture is provided elsewhere.
    *   Short salutation (use "Hello," unless a specific name is provided).
    *   **Hook:** State interest in the role and company specifically.
    *   **Body Paragraph 1 (Experience):** Connect specific requirements in the JD to the user's Work Experience (e.g., Finz, BU BIT Lab).
    *   **Body Paragraph 2 (Projects):** Connect "Technical Projects" (e.g., Multi-agent Novel Gen) to the role's needs (especially if AI/Agentic role). Uses specific tech stack details.
    *   **Closing:** Reiterate value and interest. sign-off.
3.  **Connecting the dots:** explicitly link the user's past achievements to the company's problems/stack mentioned in the JD.
4.  **Length:** ONE PAGE; 4 short paragraphs max, 4-6 sentences total.
5.  **Formatting:** Use plain text with paragraph breaks (blank lines) between paragraphs.

**Job Description:**
{job_description}

**Target Persona:**
{target_persona_json}

**Requirement Map:**
{requirement_map_json}

**Reviewer Instructions (if any):**
{reviewer_instructions}

**Master Profile:**
{profile_json}

**Output:**
Return ONLY the text of the cover letter (plain text with paragraphs).
Do NOT wrap the output in code fences.
"""

QUALITY_CRITIC_PROMPT = """
You are The Quality Critic (The Reviewer). Act as both an HR manager and an ATS scanner.

**Tasks:**
1) Check the resume is ONE PAGE length (concise, not overstuffed).
2) Ensure "Work Experience" and "Technical Projects" sections are clearly separated.
3) Score the match quality to the JD (0-100).
4) Provide specific revision instructions if score <= 85.

**Job Description:**
{job_description}

**Target Persona:**
{target_persona_json}

**Requirement Map:**
{requirement_map_json}

**Resume Draft:**
{resume_markdown}

**Cover Letter Draft:**
{cover_letter_text}

**Output (JSON only):**
{{
  "match_score": 0,
  "issues": [],
  "revision_instructions": ""
}}
"""

# --- Nodes ---

def analyze_jd(state: AgentState):
    print("--- ANALYZING JD ---")
    prompt = ChatPromptTemplate.from_template(JD_STRATEGIST_PROMPT)
    chain = prompt | llm
    response = chain.invoke({
        "job_description": state["job_description"],
    })
    target_persona = _safe_json_loads(response.content)
    print(json.dumps(target_persona, indent=2))
    return {"target_persona": target_persona}

def map_experience(state: AgentState):
    print("--- MAPPING EXPERIENCE ---")
    prompt = ChatPromptTemplate.from_template(EXPERIENCE_MATCHER_PROMPT)
    chain = prompt | llm
    response = chain.invoke({
        "job_description": state["job_description"],
        "target_persona_json": json.dumps(state.get("target_persona", {}), indent=2),
        "profile_json": json.dumps(state["profile"], indent=2),
    })
    requirement_map = _safe_json_loads(response.content)
    print(json.dumps(requirement_map, indent=2))
    return {"requirement_map": requirement_map}

def ghostwrite_resume(state: AgentState):
    print("--- GHOSTWRITING RESUME ---")
    prompt = ChatPromptTemplate.from_template(GHOSTWRITER_RESUME_PROMPT)
    chain = prompt | llm
    response = chain.invoke({
        "job_description": state["job_description"],
        "target_persona_json": json.dumps(state.get("target_persona", {}), indent=2),
        "requirement_map_json": json.dumps(state.get("requirement_map", {}), indent=2),
        "reviewer_instructions": state.get("reviewer_instructions", ""),
        "profile_json": json.dumps(state["profile"], indent=2),
    })
    return {"resume_markdown": response.content}

def ghostwrite_cover_letter(state: AgentState):
    print("--- GHOSTWRITING COVER LETTER ---")
    prompt = ChatPromptTemplate.from_template(GHOSTWRITER_COVER_LETTER_PROMPT)
    chain = prompt | llm
    response = chain.invoke({
        "job_description": state["job_description"],
        "target_persona_json": json.dumps(state.get("target_persona", {}), indent=2),
        "requirement_map_json": json.dumps(state.get("requirement_map", {}), indent=2),
        "reviewer_instructions": state.get("reviewer_instructions", ""),
        "profile_json": json.dumps(state["profile"], indent=2),
    })
    return {"cover_letter_text": response.content}

def review_quality(state: AgentState):
    print("--- REVIEWING QUALITY ---")
    prompt = ChatPromptTemplate.from_template(QUALITY_CRITIC_PROMPT)
    chain = prompt | llm
    response = chain.invoke({
        "job_description": state["job_description"],
        "target_persona_json": json.dumps(state.get("target_persona", {}), indent=2),
        "requirement_map_json": json.dumps(state.get("requirement_map", {}), indent=2),
        "resume_markdown": state.get("resume_markdown", ""),
        "cover_letter_text": state.get("cover_letter_text", ""),
    })
    critique = _safe_json_loads(response.content)
    print(json.dumps(critique, indent=2))
    match_score = critique.get("match_score", 0) if isinstance(critique, dict) else 0
    review_rounds = state.get("review_rounds", 0) + 1
    updates = {
        "critique": critique,
        "match_score": match_score,
        "reviewer_instructions": critique.get("revision_instructions", "") if isinstance(critique, dict) else "",
        "review_rounds": review_rounds,
    }
    if review_rounds == 1:
        updates.update({
            "best_resume_markdown": state.get("resume_markdown", ""),
            "best_cover_letter_text": state.get("cover_letter_text", ""),
            "best_match_score": match_score,
        })
    else:
        best_score = state.get("best_match_score", 0)
        if match_score < best_score:
            updates.update({
                "resume_markdown": state.get("best_resume_markdown", state.get("resume_markdown", "")),
                "cover_letter_text": state.get("best_cover_letter_text", state.get("cover_letter_text", "")),
                "match_score": best_score,
            })
    return updates

# --- Graph Construction ---

workflow = StateGraph(AgentState)

workflow.add_node("analyze_jd", analyze_jd)
workflow.add_node("map_experience", map_experience)
workflow.add_node("ghostwrite_resume", ghostwrite_resume)
workflow.add_node("ghostwrite_cover_letter", ghostwrite_cover_letter)
workflow.add_node("review_quality", review_quality)

workflow.set_entry_point("analyze_jd")
workflow.add_edge("analyze_jd", "map_experience")
workflow.add_edge("map_experience", "ghostwrite_resume")
workflow.add_edge("ghostwrite_resume", "ghostwrite_cover_letter")
workflow.add_edge("ghostwrite_cover_letter", "review_quality")

def _route_quality(state: AgentState):
    if state.get("match_score", 0) < 90 and state.get("review_rounds", 0) < 2:
        return "revise"
    return "done"

workflow.add_conditional_edges(
    "review_quality",
    _route_quality,
    {
        "revise": "ghostwrite_resume",
        "done": END,
    },
)

agent_workflow = workflow.compile()
