import os
import json
import csv
import shutil
import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

import auth_db

app = FastAPI(title="Redrob Talent Intelligence API")

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(WORKSPACE_DIR, "[PUB] India_runs_data_and_ai_challenge", "[PUB] India_runs_data_and_ai_challenge", "India_runs_data_and_ai_challenge")

# Initialize database at startup
@app.on_event("startup")
def startup_event():
    auth_db.init_db()

# Helper dependency to authenticate users
async def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized: No active session")
    token = authorization.split(" ")[1]
    username = auth_db.verify_session(token)
    if not username:
        raise HTTPException(status_code=401, detail="Unauthorized: Session expired or invalid")
    return username

# Helper function to resolve paths for a specific role
def get_role_paths(role_id: str | None = None) -> Dict[str, str]:
    if not role_id or role_id == "default":
        role_id = "default"
    
    role_dir = os.path.join(WORKSPACE_DIR, "roles", role_id)
    os.makedirs(role_dir, exist_ok=True)
    return {
        "jd": os.path.join(role_dir, "job_description_custom.txt"),
        "candidates": os.path.join(role_dir, "candidates_custom.jsonl"),
        "submission": os.path.join(role_dir, "team_submission.csv"),
        "default_jd": os.path.join(DATASET_DIR, "job_description.txt"),
        "default_candidates": os.path.join(DATASET_DIR, "candidates.jsonl")
    }

# Cache candidates data in memory for fast retrieval (only Top 100/sample, or stream from JSONL)
def load_candidate_by_id(candidate_id: str, role_id: str = "default") -> Dict[str, Any]:
    paths = get_role_paths(role_id)
    
    if os.path.exists(paths["candidates"]):
        candidates_file = paths["candidates"]
    else:
        candidates_file = paths["default_candidates"]
        
    if not os.path.exists(candidates_file):
        raise HTTPException(status_code=500, detail="candidates.jsonl not found")
        
    with open(candidates_file, "r", encoding="utf-8-sig") as f:
        for line in f:
            if not line.strip():
                continue
            if candidate_id in line:
                cand = json.loads(line)
                if cand["candidate_id"] == candidate_id:
                    return cand
    return {}

# ==========================================================================
# AUTH ENDPOINTS
# ==========================================================================

class AuthRequest(BaseModel):
    username: str
    password: str

@app.post("/api/auth/register")
def register(credentials: AuthRequest):
    success = auth_db.register_user(credentials.username, credentials.password)
    if not success:
        raise HTTPException(status_code=400, detail="Username already exists or invalid input.")
    return {"status": "success", "message": "User registered successfully."}

@app.post("/api/auth/login")
def login(credentials: AuthRequest):
    is_valid = auth_db.authenticate_user(credentials.username, credentials.password)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    token = auth_db.create_session(credentials.username)
    return {"status": "success", "token": token, "username": credentials.username}

@app.post("/api/auth/logout")
def logout(authorization: Optional[str] = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        auth_db.destroy_session(token)
    return {"status": "success", "message": "Logged out successfully."}

@app.get("/api/auth/me")
def get_me(username: str = Depends(get_current_user)):
    return {"status": "success", "username": username}

# ==========================================================================
# ROLES ENDPOINTS
# ==========================================================================

class RoleCreateRequest(BaseModel):
    role_id: str

@app.get("/api/roles")
def list_roles(username: str = Depends(get_current_user)):
    roles_dir = os.path.join(WORKSPACE_DIR, "roles")
    if not os.path.exists(roles_dir):
        return {"roles": ["default"]}
    
    role_list = ["default"]
    for entry in os.listdir(roles_dir):
        if os.path.isdir(os.path.join(roles_dir, entry)) and entry != "default":
            role_list.append(entry)
    return {"roles": role_list}

@app.post("/api/roles")
def create_role(request: RoleCreateRequest, username: str = Depends(get_current_user)):
    role_id = request.role_id.strip().lower().replace(" ", "_")
    if not role_id or role_id == "default":
        raise HTTPException(status_code=400, detail="Invalid role name")
        
    role_dir = os.path.join(WORKSPACE_DIR, "roles", role_id)
    if os.path.exists(role_dir):
        raise HTTPException(status_code=400, detail="Role already exists.")
        
    os.makedirs(role_dir, exist_ok=True)
    return {"status": "success", "role_id": role_id}

@app.delete("/api/roles/{role_id}")
def delete_role(role_id: str, username: str = Depends(get_current_user)):
    role_id = role_id.strip().lower()
    if role_id == "default":
        raise HTTPException(status_code=400, detail="Cannot delete default role")
        
    role_dir = os.path.join(WORKSPACE_DIR, "roles", role_id)
    if os.path.exists(role_dir):
        shutil.rmtree(role_dir)
        return {"status": "success", "message": f"Role '{role_id}' deleted successfully."}
        
    raise HTTPException(status_code=404, detail="Role not found.")

# ==========================================================================
# WORKSPACE ENDPOINTS
# ==========================================================================

@app.get("/api/job-description")
def get_job_description(role_id: str = "default", username: str = Depends(get_current_user)):
    paths = get_role_paths(role_id)
    
    if os.path.exists(paths["jd"]):
        try:
            with open(paths["jd"], "r", encoding="utf-8") as f:
                text = f.read()
            return {"content": text}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    return {"content": ""}

@app.get("/api/candidates")
def get_ranked_candidates(role_id: str = "default", username: str = Depends(get_current_user)):
    paths = get_role_paths(role_id)
    submission_path = paths["submission"]
    
    # If no ranks have been calculated for this role yet, return empty list
    if not os.path.exists(submission_path):
        return {"status": "success", "candidates": []}
        
    top_candidates = []
    
    try:
        # Load ranks, scores, and reasonings from CSV
        with open(submission_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                top_candidates.append({
                    "candidate_id": row["candidate_id"],
                    "rank": int(row["rank"]),
                    "score": float(row["score"]),
                    "reasoning": row["reasoning"]
                })
                
        # Populate full candidate profile details by scanning candidates.jsonl
        cids_to_find = {item["candidate_id"] for item in top_candidates}
        matched_profiles = {}
        
        candidates_file = paths["candidates"]
        if not os.path.exists(candidates_file):
            candidates_file = paths["default_candidates"]
            
        if os.path.exists(candidates_file):
            with open(candidates_file, "r", encoding="utf-8-sig") as f:
                for line in f:
                    if not line.strip():
                        continue
                    idx = line.find('"candidate_id"')
                    if idx != -1:
                        start = line.find('"', idx + 14)
                        if start != -1:
                            end = line.find('"', start + 1)
                            if end != -1:
                                cid = line[start+1:end]
                                if cid in cids_to_find:
                                    matched_profiles[cid] = json.loads(line)
                                    if len(matched_profiles) == len(cids_to_find):
                                        break
                            
        for item in top_candidates:
            cid = item["candidate_id"]
            if cid in matched_profiles:
                item["details"] = matched_profiles[cid]
            else:
                item["details"] = {"candidate_id": cid, "profile": {"anonymized_name": "Unknown Candidate", "headline": "Unavailable"}}
                
        return {"status": "success", "candidates": top_candidates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/candidate/{candidate_id}")
def get_candidate_details(candidate_id: str, role_id: str = "default", username: str = Depends(get_current_user)):
    try:
        cand = load_candidate_by_id(candidate_id, role_id)
        if not cand:
            raise HTTPException(status_code=404, detail="Candidate not found")
        return cand
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/rank")
def trigger_ranking(role_id: str = "default", username: str = Depends(get_current_user)):
    import subprocess
    paths = get_role_paths(role_id)
    
    if not os.path.exists(paths["candidates"]):
        raise HTTPException(status_code=400, detail="No candidate pool found. Please upload a candidates pool CSV or JSONL first.")
        
    if not os.path.exists(paths["jd"]):
        raise HTTPException(status_code=400, detail="No job description saved. Please type and save a Job Description first.")
        
    try:
        candidates_file = paths["candidates"]
        out_file = paths["submission"]
        
        # Execute rank.py using subprocess
        cmd = [
            "python", "rank.py",
            "--candidates", candidates_file,
            "--out", out_file,
            "--jd", paths["jd"]
        ]
            
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return {"status": "success", "message": f"Ranking calculated successfully for role '{role_id}'."}
    except Exception as e:
        stderr = getattr(e, "stderr", "")
        raise HTTPException(status_code=500, detail=f"Ranking execution failed: {str(e)}. Stderr: {stderr}")

@app.get("/api/status")
def get_status(role_id: str = "default", username: str = Depends(get_current_user)):
    paths = get_role_paths(role_id)
    
    has_custom_jd = os.path.exists(paths["jd"])
    has_custom_candidates = os.path.exists(paths["candidates"])
    
    candidates_count = 0
    if has_custom_candidates:
        try:
            with open(paths["candidates"], "r", encoding="utf-8-sig") as f:
                candidates_count = sum(1 for line in f if line.strip())
        except Exception:
            pass
            
    return {
        "has_custom_jd": has_custom_jd,
        "has_custom_candidates": has_custom_candidates,
        "candidates_count": candidates_count
    }

class JobDescriptionUpdate(BaseModel):
    content: str
    role_id: str = "default"

@app.post("/api/job-description")
def update_job_description(jd: JobDescriptionUpdate, username: str = Depends(get_current_user)):
    try:
        paths = get_role_paths(jd.role_id)
        with open(paths["jd"], "w", encoding="utf-8") as f:
            f.write(jd.content)
        return {"status": "success", "message": f"Job description updated successfully for role '{jd.role_id}'."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def convert_csv_to_jsonl(csv_content: str, output_path: str) -> int:
    import io
    import csv
    
    reader = csv.DictReader(io.StringIO(csv_content))
    fieldnames = reader.fieldnames or []
    field_map = {f.strip().lower().replace("_", ""): f for f in fieldnames}
    
    def get_val(row, aliases, default=""):
        for alias in aliases:
            norm_alias = alias.lower().replace("_", "")
            if norm_alias in field_map:
                val = row[field_map[norm_alias]]
                if val is not None:
                    return str(val).strip()
        return default
        
    candidates = []
    
    for idx, row in enumerate(reader):
        cid = get_val(row, ["candidate_id", "id"], f"CAND_CSV_{idx+1:05d}")
        name = get_val(row, ["name", "anonymized_name"], "Unknown Candidate")
        title = get_val(row, ["title", "current_title", "role"], "Software Engineer")
        company = get_val(row, ["company", "current_company", "employer"], "Company")
        
        yoe_str = get_val(row, ["yoe", "years_of_experience", "experience"], "0")
        try:
            yoe = float(yoe_str)
        except ValueError:
            yoe = 0.0
            
        location = get_val(row, ["location", "city"], "India")
        country = get_val(row, ["country"], "India")
        
        skills_str = get_val(row, ["skills", "skill_list"], "")
        skills_list = []
        if skills_str:
            for s in skills_str.split(","):
                s = s.strip()
                if s:
                    skills_list.append({
                        "name": s,
                        "proficiency": "advanced",
                        "endorsements": 5,
                        "duration_months": 12
                    })
                    
        summary = get_val(row, ["summary", "headline", "bio"], f"{title} at {company}")
        
        notice_str = get_val(row, ["notice_period_days", "notice_period", "notice"], "30")
        try:
            notice_period = int(notice_str)
        except ValueError:
            notice_period = 30
            
        github_str = get_val(row, ["github_activity_score", "github_score", "github"], "-1")
        try:
            github_score = float(github_str)
        except ValueError:
            github_score = -1.0
            
        resp_str = get_val(row, ["recruiter_response_rate", "response_rate"], "0.5")
        try:
            resp_rate = float(resp_str)
            if resp_rate > 1.0:
                resp_rate = resp_rate / 100.0
        except ValueError:
            resp_rate = 0.5
            
        completion_str = get_val(row, ["interview_completion_rate", "completion_rate"], "0.5")
        try:
            completion_rate = float(completion_str)
            if completion_rate > 1.0:
                completion_rate = completion_rate / 100.0
        except ValueError:
            completion_rate = 0.5
            
        open_str = get_val(row, ["open_to_work_flag", "open_to_work", "open"], "true").lower()
        open_to_work = open_str in ["true", "1", "yes", "y"]
        
        career_history = []
        if company or title:
            career_history.append({
                "company": company,
                "title": title,
                "duration_months": int(yoe * 12) if yoe > 0 else 12,
                "is_current": True,
                "description": summary
            })
            
        cand_obj = {
            "candidate_id": cid,
            "profile": {
                "anonymized_name": name,
                "headline": summary,
                "summary": summary,
                "location": location,
                "country": country,
                "years_of_experience": yoe,
                "current_title": title,
                "current_company": company
            },
            "career_history": career_history,
            "education": [],
            "skills": skills_list,
            "certifications": [],
            "languages": [],
            "redrob_signals": {
                "profile_completeness_score": 80.0,
                "signup_date": "2025-01-01",
                "last_active_date": "2026-06-27",
                "open_to_work_flag": open_to_work,
                "recruiter_response_rate": resp_rate,
                "avg_response_time_hours": 24.0,
                "github_activity_score": github_score,
                "interview_completion_rate": completion_rate,
                "notice_period_days": notice_period
            }
        }
        candidates.append(cand_obj)
        
    with open(output_path, "w", encoding="utf-8") as f:
        for c in candidates:
            f.write(json.dumps(c) + "\n")
            
    return len(candidates)

@app.post("/api/upload-candidates")
def upload_candidates(role_id: str = "default", file: UploadFile = File(...), username: str = Depends(get_current_user)):
    if not (file.filename.endswith(".jsonl") or file.filename.endswith(".csv")):
        raise HTTPException(status_code=400, detail="Only .jsonl or .csv files are allowed.")
        
    try:
        paths = get_role_paths(role_id)
        custom_candidates_path = paths["candidates"]
        
        if file.filename.endswith(".jsonl"):
            with open(custom_candidates_path, "wb") as f:
                while content := file.file.read(1024 * 1024):
                    f.write(content)
            return {"status": "success", "message": f"Candidates pool JSONL uploaded successfully for role '{role_id}'."}
        else:
            content_bytes = file.file.read()
            try:
                content_str = content_bytes.decode("utf-8-sig")
            except UnicodeDecodeError:
                content_str = content_bytes.decode("latin-1")
                
            count = convert_csv_to_jsonl(content_str, custom_candidates_path)
            return {
                "status": "success",
                "message": f"Successfully parsed and converted CSV. Loaded {count} candidates for role '{role_id}'."
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/reset")
def reset_workspace(role_id: str = "default", username: str = Depends(get_current_user)):
    paths = get_role_paths(role_id)
    
    try:
        # Load sample demo sandbox data into the role path
        # 1. Job Description
        default_jd_path = os.path.join(DATASET_DIR, "job_description.txt")
        if os.path.exists(default_jd_path):
            shutil.copy(default_jd_path, paths["jd"])
            
        # 2. Candidates JSONL (use candidates_sample.jsonl which is small and fast)
        sample_cand_path = os.path.join(WORKSPACE_DIR, "candidates_sample.jsonl")
        if os.path.exists(sample_cand_path):
            shutil.copy(sample_cand_path, paths["candidates"])
            
        # 3. Submission CSV
        sample_sub_path = os.path.join(WORKSPACE_DIR, "team_submission_sample.csv")
        if os.path.exists(sample_sub_path):
            shutil.copy(sample_sub_path, paths["submission"])
            
        return {"status": "success", "message": f"Demo sandbox dataset loaded successfully for role '{role_id}'."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load demo sandbox data: {str(e)}")

# ==========================================================================
# AI CHAT ASSISTANT ENDPOINT
# ==========================================================================

class ChatRequest(BaseModel):
    message: str
    role_id: str = "default"
    gemini_api_key: Optional[str] = None

def get_fallback_bot_response(message: str, jd: str, candidates: List[Dict[str, Any]]) -> str:
    msg_lower = message.lower()
    
    profiles = []
    for c in candidates:
        profile = c.get("details", {}).get("profile", {})
        signals = c.get("details", {}).get("redrob_signals", {})
        skills = [s.get("name", "") for s in c.get("details", {}).get("skills", [])]
        profiles.append({
            "id": c["candidate_id"],
            "rank": c["rank"],
            "score": c["score"],
            "reasoning": c["reasoning"],
            "name": profile.get("anonymized_name", "Unknown"),
            "title": profile.get("current_title", "Software Engineer"),
            "company": profile.get("current_company", "Company"),
            "yoe": profile.get("years_of_experience", 0),
            "location": profile.get("location", "India"),
            "notice": signals.get("notice_period_days", 30),
            "response_rate": int(signals.get("recruiter_response_rate", 0) * 100),
            "github": signals.get("github_activity_score", -1),
            "completion": int(signals.get("interview_completion_rate", 0) * 100),
            "skills": skills
        })
        
    if not profiles:
        return "It looks like there are no candidates indexed for this role yet. Please upload candidate data and run the ranker first."
        
    # Check for compare queries
    if "compare" in msg_lower:
        found = []
        for p in profiles:
            if p["id"].lower() in msg_lower or str(p["rank"]) in msg_lower or p["name"].lower() in msg_lower:
                found.append(p)
        if len(found) < 2 and len(profiles) >= 2:
            found = profiles[:2]
            
        if len(found) >= 2:
            res = f"### Candidate Comparison Matrix\n\n"
            res += "| Parameter | " + " | ".join([f"#{p['rank']} - {p['name']}" for p in found]) + " |\n"
            res += "| :--- | " + " | ".join([":---:" for _ in found]) + " |\n"
            res += f"| **Score** | " + " | ".join([f"{p['score']:.4f}" for p in found]) + " |\n"
            res += f"| **Role / Title** | " + " | ".join([f"{p['title']}" for p in found]) + " |\n"
            res += f"| **Company** | " + " | ".join([f"{p['company']}" for p in found]) + " |\n"
            res += f"| **Experience (YoE)** | " + " | ".join([f"{p['yoe']} Years" for p in found]) + " |\n"
            res += f"| **Notice Period** | " + " | ".join([f"{p['notice']} Days" for p in found]) + " |\n"
            res += f"| **Response Rate** | " + " | ".join([f"{p['response_rate']}%" for p in found]) + " |\n"
            res += f"| **GitHub Score** | " + " | ".join([f"{p['github'] if p['github'] != -1 else 'N/A'}" for p in found]) + " |\n"
            res += f"| **Skills** | " + " | ".join([f"{', '.join(p['skills'][:3])}" for p in found]) + " |\n\n"
            res += "**Key Analysis:**\n"
            p1, p2 = found[0], found[1]
            if p1["score"] > p2["score"]:
                res += f"- **{p1['name']}** is ranked higher (Score: {p1['score']}) mainly due to alignment with core experience bands or product company background.\n"
            res += f"- **{p2['name']}** has a notice period of {p2['notice']} days compared to {p1['name']}'s {p1['notice']} days.\n"
            return res
        return "I found the compare query, but I couldn't identify at least two candidates in the database to compare. Please specify candidate IDs (e.g. 'CAND_00001')."
        
    # Check for email queries
    if "email" in msg_lower or "outreach" in msg_lower or "draft" in msg_lower:
        cand = profiles[0]
        for p in profiles:
            if p["id"].lower() in msg_lower or p["name"].lower() in msg_lower or f"#{p['rank']}" in msg_lower:
                cand = p
                break
                
        email = f"**Subject:** Exciting Founding Team Opportunity - Senior AI Engineer at Redrob\n\n"
        email += f"Hi {cand['name']},\n\n"
        email += f"I hope this message finds you well.\n\n"
        email += f"I was reviewing your impressive background, particularly your tenure as a **{cand['title']}** at **{cand['company']}** and your {cand['yoe']} years of experience. We are currently building a founding AI team, and your expertise in **{', '.join(cand['skills'][:3])}** aligns exceptionally well with our technical challenges.\n\n"
        if cand['github'] > 40:
            email += f"I also noticed your strong contributions on GitHub (Activity Score: {cand['github']}), which represents the high-signal builder mindset we value.\n\n"
        email += f"Since your notice period is {cand['notice']} days, we would love to connect for a quick 15-minute conversation to explore if there is mutual alignment.\n\n"
        email += "Are you free for a call sometime this week?\n\n"
        email += "Best regards,\n[Recruiter Name]\nRedrob Talent Intelligence"
        return f"Here is a personalized outreach email draft for **{cand['name']}** (Rank #{cand['rank']}):\n\n---\n\n{email}"

    # Check for skills queries
    skills_query = []
    for s in ["python", "pytorch", "embeddings", "vector", "rag", "eval", "ml", "nlp", "llm"]:
        if s in msg_lower:
            skills_query.append(s)
    if skills_query:
        matches = []
        for p in profiles:
            for sq in skills_query:
                if any(sq in sk.lower() for sk in p["skills"]):
                    matches.append(p)
                    break
        if matches:
            res = f"Here are the candidates matching skills **{', '.join(skills_query)}**:\n\n"
            for m in matches[:5]:
                res += f"- **#{m['rank']} - {m['name']}** (Score: {m['score']}): Knows {', '.join([s for s in m['skills'] if any(sq in s.lower() for sq in skills_query)])}\n"
            return res
        return f"I searched the profiles but could not find any candidates with verified skills matching **{', '.join(skills_query)}**."

    # Check for notice/availability queries
    if "notice" in msg_lower or "availability" in msg_lower or "fastest" in msg_lower or "quickest" in msg_lower:
        sorted_by_notice = sorted(profiles, key=lambda x: x["notice"])
        res = "### Candidates Sorted by Notice Period (Fastest Availability):\n\n"
        for m in sorted_by_notice[:5]:
            res += f"- **#{m['rank']} - {m['name']}**: {m['notice']} Days notice period (Score: {m['score']})\n"
        return res

    # Check for GitHub queries
    if "github" in msg_lower or "open source" in msg_lower or "git" in msg_lower:
        sorted_by_git = sorted([p for p in profiles if p["github"] != -1], key=lambda x: -x["github"])
        if sorted_by_git:
            res = "### Top Open-Source / GitHub Contributors:\n\n"
            for m in sorted_by_git[:5]:
                res += f"- **#{m['rank']} - {m['name']}**: GitHub Activity Score of **{m['github']}** (Score: {m['score']})\n"
            return res
        return "No candidates in the top shortlist have a verified GitHub account connected."
        
    # Check for top candidates / why query
    if "top" in msg_lower or "best" in msg_lower or "why" in msg_lower or "reason" in msg_lower:
        cand = profiles[0]
        for p in profiles:
            if p["id"].lower() in msg_lower or p["name"].lower() in msg_lower or f"#{p['rank']}" in msg_lower:
                cand = p
                break
        res = f"### Profile Fit Analysis: {cand['name']} (Rank #{cand['rank']})\n\n"
        res += f"- **Experience**: {cand['yoe']} Years of Experience as a {cand['title']} at {cand['company']}.\n"
        res += f"- **AI Score**: {cand['score']:.4f}\n"
        res += f"- **AI Reasoning**: {cand['reasoning']}\n\n"
        res += f"**Verdict**: A highly matching profile based on dense semantic alignment with the Job Description."
        return res

    return (
        f"Hello! I am your AI Recruiter Assistant. I have analyzed the active Job Description "
        f"and the candidate pool of **{len(profiles)}** shortlisted profiles.\n\n"
        f"Here are some examples of what you can ask me:\n"
        f"1. **\"Who is the top candidate and why?\"**\n"
        f"2. **\"Compare candidates CAND_00001 and CAND_00002\"**\n"
        f"3. **\"Draft an outreach email to the top candidate\"**\n"
        f"4. **\"Who has Python or PyTorch skills?\"**\n"
        f"5. **\"Which candidates have the fastest availability (lowest notice period)?\"**\n\n"
        f"*Note: Enter your Gemini API Key in the settings input to unlock full natural language reasoning.*"
    )

@app.post("/api/ai/chat")
async def chat_assistant(
    request: ChatRequest, 
    username: str = Depends(get_current_user),
    x_gemini_key: Optional[str] = Header(None)
):
    api_key = x_gemini_key or request.gemini_api_key or os.environ.get("GEMINI_API_KEY")
    
    try:
        jd_res = get_job_description(request.role_id, username)
        jd_text = jd_res.get("content", "")
    except Exception:
        jd_text = ""
        
    try:
        cand_res = get_ranked_candidates(request.role_id, username)
        candidates = cand_res.get("candidates", [])
    except Exception:
        candidates = []
        
    if not api_key:
        response_text = get_fallback_bot_response(request.message, jd_text, candidates)
        return {"status": "success", "response": response_text, "engine": "local_fallback"}
        
    cand_summary_list = []
    for c in candidates[:15]:
        profile = c.get("details", {}).get("profile", {})
        signals = c.get("details", {}).get("redrob_signals", {})
        skills = ", ".join([s.get("name", "") for s in c.get("details", {}).get("skills", [])])
        
        cand_summary_list.append(
            f"Rank #{c['rank']} (Score: {c['score']:.4f}) - Candidate ID: {c['candidate_id']}\n"
            f"Name: {profile.get('anonymized_name', 'Unknown')}\n"
            f"Title: {profile.get('current_title', 'Software Engineer')} at {profile.get('current_company', 'Company')}\n"
            f"YoE: {profile.get('years_of_experience', 0)} years | Location: {profile.get('location', 'India')}\n"
            f"Skills: {skills}\n"
            f"Notice Period: {signals.get('notice_period_days', 30)} days | Recruiter Response: {int(signals.get('recruiter_response_rate', 0)*100)}% | GitHub Activity: {signals.get('github_activity_score', -1)} | Interview Completion: {int(signals.get('interview_completion_rate', 0)*100)}%\n"
            f"AI Match Justification: {c['reasoning']}\n"
        )
        
    candidates_context = "\n---\n".join(cand_summary_list)
    
    system_prompt = (
        "You are an advanced AI Recruiter Assistant integrated inside REDROB Talent Intelligence dashboard.\n"
        "You help recruitment teams query, compare, shortlist, analyze, and draft outreach emails for candidates.\n\n"
        f"ACTIVE TARGET JOB DESCRIPTION:\n{jd_text}\n\n"
        f"SHORTLISTED CANDIDATES (TOP 15):\n{candidates_context}\n\n"
        "INSTRUCTIONS:\n"
        "1. Base your answers strictly on the candidates list and JD provided above.\n"
        "2. If requested to draft outreach emails, make them highly personalized, professional, and highlight candidate's specific current title, company, skills, notice period, and GitHub activity score.\n"
        "3. If compared, build a markdown table highlighting metrics.\n"
        "4. Be clear, concise, and professional."
    )
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": f"{system_prompt}\n\nUser Question: {request.message}"}]
            }
        ]
    }
    
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(url, headers=headers, json=payload, timeout=30.0)
            
        if res.status_code != 200:
            err_msg = f"Gemini API returned status {res.status_code}: {res.text}"
            print(f"Warning: {err_msg}")
            fallback_text = get_fallback_bot_response(request.message, jd_text, candidates)
            return {
                "status": "success", 
                "response": f"*(Gemini API Error, falling back to Local Engine)*\n\n{fallback_text}", 
                "engine": "local_fallback"
            }
            
        res_data = res.json()
        response_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
        return {"status": "success", "response": response_text, "engine": "gemini-2.5-flash"}
        
    except Exception as e:
        fallback_text = get_fallback_bot_response(request.message, jd_text, candidates)
        return {
            "status": "success", 
            "response": f"*(Network Error, falling back to Local Engine: {str(e)})*\n\n{fallback_text}", 
            "engine": "local_fallback"
        }

# ==========================================================================
# STATIC FRONTEND SERVING
# ==========================================================================

frontend_dist = os.path.join(WORKSPACE_DIR, "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host=host, port=port)
