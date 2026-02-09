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
You are the **JD Strategist**. Your goal is to reverse-engineer the Job Description to identify what the hiring manager truly values.

**Tasks:**
1) **Target Persona:** Identify the specific archetype (e.g., "Systems-Heavy Backend Engineer", "AI Orchestration Specialist", "Data Infrastructure Architect").
2) **Pain Points:** What technical problems is the company trying to solve? (e.g., Scaling real-time data, LLM reliability, high-performance storage).
3) **Keyword Taxonomy:** Extract Must-Have vs. Nice-to-Have skills. Prioritize tools like Spark, Kafka, or specific cloud providers (AWS/Azure).
4) **Culture Signals:** Is this a fast-paced startup (emphasize "end-to-end delivery") or a large enterprise (emphasize "standards, documentation, and scalability")?

**Job Description:**
{job_description}

**Output (JSON only):**
{{
  "persona": "",
  "core_pain_points": [],
  "must_have_skills": [],
  "nice_to_have_skills": [],
  "strategic_focus": "e.g., emphasize systems engineering over web dev"
}}
"""

EXPERIENCE_MATCHER_PROMPT = """
You are the **Experience Matcher**. You are a career strategist mapping a candidate's "Master Profile" to a specific "Job Description."

**Rules:**
1) **Strategic Selection:** Choose the most relevant 4-6 entries total (mix of work + projects).
2) **Technical Mapping:** Map specific accomplishments to JD requirements.
3) **Conciseness:** Keep each "reasoning" to one short sentence.
4) **No Hallucinations:** Use ONLY the facts provided in the Master Profile.

**Target Persona:** {target_persona_json}
**Job Description:** {job_description}
**Master Profile:** {profile_json}

**Output (JSON only):**
{{
  "selected_entries": [
    {{
      "id": "project_title_or_job_name",
      "reasoning": "Why this matches a specific JD requirement",
      "key_metrics_to_include": ["e.g., 20% accuracy gain", "30% token reduction"]
    }}
  ]
}}
"""

GHOSTWRITER_RESUME_PROMPT = """
You are an expert **Technical Resume Writer** for the US Silicon Valley market. Your goal is to generate a one-page Markdown resume.

**The Google XYZ Formula (Preferred):**
When a metric exists in the Master Profile, use: "Accomplished [X] as measured by [Y], by doing [Z]."
- *X (Action):* Start with a strong action verb (Architected, Engineered, Optimized).
- *Y (Metric):* Use real metrics only if present in the profile.
- *Z (How):* Mention specific technologies (LangGraph, C++20, Kafka, AWS).
If no metric exists, omit [Y] and keep the bullet factual and concise.

**Format Requirements:**
1) **Do NOT include header/contact info.** Header is provided elsewhere.
2) **Sections:** Use `## Summary`, `## Work Experience`, `## Technical Projects`, `## Skills`, `## Education`, `## Honors & Awards`.
3) **Separation:** Strictly separate "Work Experience" from "Technical Projects".
4) **Heading Format:** `### **Role at Company** <span>Dates</span>`
5) **Location Line:** Put `*Location*` on the next line.
6) **List Spacing:** Insert a blank line between the location line and the bullet list.
7) **Bullets:** Use "-" for bullets. Max 3 bullets for work, 2 for projects. One line each (~18 words).
8) **Coverage:** Include ALL roles from the Master Profile.

**Priority Instructions (from Reviewer):**
{reviewer_instructions}

**Requirement Map:**
{requirement_map_json}

**Master Profile:** {profile_json}

**Output:** Return ONLY Markdown.
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
You are the **Quality Critic**. Grade this resume based on US Technical Recruitment standards.

**Checklist:**
1. **One-Page Rule:** Is the content concise enough to fit on one physical page?
2. **XYZ Formula:** Does every bullet point contain a metric and a specific technology?
3. **Hallucination Check:** Did the writer add any skills (e.g., "Kubernetes") that are NOT in the Master Profile?.
4. **Visual Check:** Are the dates right-aligned? Is the tech stack line distinct? Are there any typos like "PriceSentiment"?

**Scoring:**
- Match Score (0-100).
- If score < 80, you MUST provide "Revision Instructions" to the Ghostwriter.

**Draft Resume:** {resume_markdown}
**Target Persona:** {target_persona_json}
**Profile json:** {profile_json}

**Output (JSON only):**
{{
  "match_score": 0,
  "issues_found": [],
  "revision_instructions": "e.g., 'The Finz intern bullets are too long. Shorten and add a metric for the Kafka pipeline.'"
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
        "profile_json": json.dumps(state["profile"], indent=2),
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
