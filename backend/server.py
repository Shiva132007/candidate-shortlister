import os
import sys
import json
import csv
import shutil
import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# Resolve directory paths for backend execution
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(SCRIPT_DIR) == "backend":
    WORKSPACE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
    if SCRIPT_DIR not in sys.path:
        sys.path.insert(0, SCRIPT_DIR)
else:
    WORKSPACE_DIR = SCRIPT_DIR

import auth_db

app = FastAPI(title="AI-Screening Enginee Talent Intelligence API")

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        "dir": role_dir,
        "candidates": os.path.join(role_dir, "candidates_custom.jsonl"),
        "jd": os.path.join(role_dir, "job_description_custom.txt"),
        "parsed_jd": os.path.join(role_dir, "job_description_parsed.json"),
        "submission": os.path.join(role_dir, "team_submission.csv"),
        "default_candidates": os.path.join(WORKSPACE_DIR, "candidates_sample.jsonl"),
        "default_jd": os.path.join(WORKSPACE_DIR, "job_description_default.txt"),
        "default_submission": os.path.join(WORKSPACE_DIR, "team_submission_sample.csv")
    }

def load_candidate_by_id(candidate_id: str, role_id: str = "default") -> Dict[str, Any]:
    paths = get_role_paths(role_id)
    candidates_file = paths["candidates"]
    if not os.path.exists(candidates_file):
        candidates_file = paths["default_candidates"]
        
    if os.path.exists(candidates_file):
        with open(candidates_file, "r", encoding="utf-8-sig") as f:
            for line in f:
                if not line.strip():
                    continue
                cand = json.loads(line)
                if cand.get("candidate_id") == candidate_id:
                    return cand
    return {}

# Pydantic schemas for auth and request payloads
class AuthRequest(BaseModel):
    username: str
    password: str

class RoleCreateRequest(BaseModel):
    role_id: str

class JobDescriptionUpdate(BaseModel):
    role_id: Optional[str] = "default"
    jd_text: str

class ChatMessage(BaseModel):
    role_id: Optional[str] = "default"
    message: str

# Auth endpoints
@app.post("/api/auth/register")
def register(credentials: AuthRequest):
    success = auth_db.register_user(credentials.username, credentials.password)
    if not success:
        raise HTTPException(status_code=400, detail="Username already exists or invalid password")
    token = auth_db.create_session(credentials.username)
    return {"status": "success", "token": token, "username": credentials.username}

@app.post("/api/auth/login")
def login(credentials: AuthRequest):
    authenticated = auth_db.authenticate_user(credentials.username, credentials.password)
    if not authenticated:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = auth_db.create_session(credentials.username)
    return {"status": "success", "token": token, "username": credentials.username}

@app.post("/api/auth/logout")
def logout(authorization: Optional[str] = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        auth_db.delete_session(token)
    return {"status": "success"}

@app.get("/api/auth/me")
def get_me(username: str = Depends(get_current_user)):
    return {"status": "success", "username": username}

# Multi-Role workspace management endpoints
@app.get("/api/roles")
def list_roles(username: str = Depends(get_current_user)):
    roles_dir = os.path.join(WORKSPACE_DIR, "roles")
    if not os.path.exists(roles_dir):
        os.makedirs(roles_dir, exist_ok=True)
        os.makedirs(os.path.join(roles_dir, "default"), exist_ok=True)
        
    roles = [d for d in os.listdir(roles_dir) if os.path.isdir(os.path.join(roles_dir, d))]
    if "default" not in roles:
        roles.insert(0, "default")
    return {"status": "success", "roles": roles}

@app.post("/api/roles")
def create_role(request: RoleCreateRequest, username: str = Depends(get_current_user)):
    role_id = request.role_id.strip().lower().replace(" ", "_")
    if not role_id or not role_id.isalnum() and "_" not in role_id:
        raise HTTPException(status_code=400, detail="Role ID must contain only letters, numbers, and underscores.")
        
    role_dir = os.path.join(WORKSPACE_DIR, "roles", role_id)
    if os.path.exists(role_dir):
        raise HTTPException(status_code=400, detail="Role workspace already exists.")
        
    os.makedirs(role_dir, exist_ok=True)
    return {"status": "success", "role_id": role_id}

@app.delete("/api/roles/{role_id}")
def delete_role(role_id: str, username: str = Depends(get_current_user)):
    if role_id == "default":
        raise HTTPException(status_code=400, detail="Cannot delete default role workspace.")
        
    role_dir = os.path.join(WORKSPACE_DIR, "roles", role_id)
    if not os.path.exists(role_dir):
        raise HTTPException(status_code=404, detail="Role workspace not found.")
        
    shutil.rmtree(role_dir)
    return {"status": "success", "message": f"Role '{role_id}' deleted."}

# Workspace data management endpoints
@app.get("/api/job-description")
def get_job_description(role_id: str = "default", username: str = Depends(get_current_user)):
    paths = get_role_paths(role_id)
    jd_path = paths["jd"]
    if not os.path.exists(jd_path):
        jd_path = paths["default_jd"]
        
    if os.path.exists(jd_path):
        with open(jd_path, "r", encoding="utf-8") as f:
            return {"status": "success", "job_description": f.read()}
    
    # Fallback default JD query text
    default_text = (
        "Senior AI Engineer Founding Team applied ML embeddings-based retrieval systems "
        "sentence-transformers vector databases Pinecone Weaviate Qdrant Milvus FAISS "
        "hybrid search Python ranking systems evaluation frameworks NDCG MRR MAP learning-to-rank "
        "LLM fine-tuning LoRA QLoRA PEFT"
    )
    return {"status": "success", "job_description": default_text}

@app.get("/api/parsed-job-description")
def get_parsed_job_description(role_id: str = "default", username: str = Depends(get_current_user)):
    paths = get_role_paths(role_id)
    parsed_path = paths["parsed_jd"]
    if os.path.exists(parsed_path):
        try:
            with open(parsed_path, "r", encoding="utf-8") as f:
                return {"status": "success", "parsed_jd": json.load(f)}
        except Exception:
            pass
            
    # Default fallback parsed JD structure
    return {
        "status": "success",
        "parsed_jd": {
            "title": "Senior AI Engineer (Founding Team)",
            "experience_min": 5,
            "experience_max": 9,
            "tech_skills": ["python", "pytorch"],
            "ir_skills": ["embeddings", "vector database", "rag"],
            "behavioral_priorities": ["immediate availability", "high response rate"]
        }
    }

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
                
        # Load extra details JSON metadata
        details_path = submission_path.replace(".csv", "_details.json")
        extra_details = {}
        if os.path.exists(details_path):
            try:
                with open(details_path, "r", encoding="utf-8") as f:
                    extra_details = json.load(f)
            except Exception:
                pass
                
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
                
            # Merge extra details metadata
            if cid in extra_details:
                item["requirements_breakdown"] = extra_details[cid].get("requirements_breakdown", [])
                item["confidence_score"] = extra_details[cid].get("confidence_score", item["score"] * 100)
                item["why_cards"] = extra_details[cid].get("why_cards", {"pros": [], "cons": []})
                item["skill_gap"] = extra_details[cid].get("skill_gap", {"matching": [], "missing": []})
                item["honeypot_reason"] = extra_details[cid].get("honeypot_reason", None)
                
        return {"status": "success", "candidates": top_candidates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/candidates/{candidate_id}")
def get_candidate_details(candidate_id: str, role_id: str = "default", username: str = Depends(get_current_user)):
    cand = load_candidate_by_id(candidate_id, role_id)
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate profile not found.")
    return {"status": "success", "candidate": cand}

@app.get("/api/download-submission")
def download_submission_csv(role_id: str = "default", username: str = Depends(get_current_user)):
    from fastapi.responses import FileResponse
    paths = get_role_paths(role_id)
    submission_path = paths["submission"]
    
    if os.path.exists(submission_path):
        return FileResponse(
            path=submission_path, 
            filename=f"team_submission_{role_id}.csv", 
            media_type="text/csv"
        )
    else:
        raise HTTPException(status_code=404, detail="No submission CSV generated yet. Please run the ranker first.")

@app.post("/api/rank")
def trigger_ranking(
    role_id: str = "default", 
    username: str = Depends(get_current_user),
    x_gemini_key: Optional[str] = Header(None)
):
    import subprocess
    paths = get_role_paths(role_id)
    
    if not os.path.exists(paths["candidates"]):
        raise HTTPException(status_code=400, detail="No candidate pool found. Please upload a candidates pool CSV or JSONL first.")
        
    if not os.path.exists(paths["jd"]):
        raise HTTPException(status_code=400, detail="No job description saved. Please type and save a Job Description first.")
        
    try:
        candidates_file = paths["candidates"]
        out_file = paths["submission"]
        
        api_key = x_gemini_key or os.environ.get("GEMINI_API_KEY")
        env = os.environ.copy()
        if api_key:
            env["GEMINI_API_KEY"] = api_key
            
        rank_script = os.path.join(SCRIPT_DIR, "rank.py") if os.path.exists(os.path.join(SCRIPT_DIR, "rank.py")) else os.path.join(WORKSPACE_DIR, "rank.py")
        
        cmd = [
            sys.executable, rank_script,
            "--candidates", candidates_file,
            "--out", out_file,
            "--jd", paths["jd"]
        ]
            
        res = subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
        return {"status": "success", "message": f"Ranking calculated successfully for role '{role_id}'."}
    except Exception as e:
        stderr = getattr(e, "stderr", "")
        raise HTTPException(status_code=500, detail=f"Ranking execution failed: {str(e)}. Stderr: {stderr}")

@app.get("/api/status")
def get_status(role_id: str = "default", username: str = Depends(get_current_user)):
    paths = get_role_paths(role_id)
    
    has_candidates = os.path.exists(paths["candidates"]) or os.path.exists(paths["default_candidates"])
    has_jd = os.path.exists(paths["jd"]) or os.path.exists(paths["default_jd"])
    has_submission = os.path.exists(paths["submission"]) or os.path.exists(paths["default_submission"])
    
    cand_count = 0
    if os.path.exists(paths["candidates"]):
        with open(paths["candidates"], "r", encoding="utf-8-sig") as f:
            cand_count = sum(1 for line in f if line.strip())
    elif os.path.exists(paths["default_candidates"]):
        with open(paths["default_candidates"], "r", encoding="utf-8-sig") as f:
            cand_count = sum(1 for line in f if line.strip())
            
    return {
        "status": "success",
        "role_id": role_id,
        "has_candidates": has_candidates,
        "has_jd": has_jd,
        "has_submission": has_submission,
        "candidate_count": cand_count
    }

@app.post("/api/job-description")
def update_job_description(jd: JobDescriptionUpdate, username: str = Depends(get_current_user)):
    role_id = jd.role_id or "default"
    paths = get_role_paths(role_id)
    
    with open(paths["jd"], "w", encoding="utf-8") as f:
        f.write(jd.jd_text)
        
    return {"status": "success", "message": f"Job description updated for role '{role_id}'."}

def convert_csv_to_jsonl(csv_content: str, output_path: str) -> int:
    import io
    
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
        for key in ["candidates", "jd", "parsed_jd", "submission"]:
            if os.path.exists(paths[key]):
                os.remove(paths[key])
        details_path = paths["submission"].replace(".csv", "_details.json")
        if os.path.exists(details_path):
            os.remove(details_path)
        return {"status": "success", "message": f"Role '{role_id}' workspace reset to defaults."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_fallback_bot_response(message: str, jd: str, candidates: List[Dict[str, Any]]) -> str:
    msg_lower = message.lower()
    
    # 1. Compare query
    if "compare" in msg_lower or "versus" in msg_lower or " vs " in msg_lower:
        found = []
        for c in candidates:
            p = c.get("details", {}).get("profile", {})
            name = p.get("anonymized_name", f"Candidate {c['candidate_id']}")
            cid = c["candidate_id"]
            if cid.lower() in msg_lower or str(c["rank"]) in msg_lower or name.lower() in msg_lower:
                found.append({
                    "id": cid,
                    "name": name,
                    "rank": c["rank"],
                    "score": f"{c['score']:.4f}",
                    "yoe": p.get("years_of_experience", 0),
                    "company": p.get("current_company", "N/A"),
                    "title": p.get("current_title", "N/A"),
                    "notice": c.get("details", {}).get("redrob_signals", {}).get("notice_period_days", "N/A")
                })
                
        if len(found) >= 2:
            res = "### Candidate Comparison Matrix\n\n"
            res += "| Parameter | " + " | ".join([f"#{p['rank']} - {p['name']}" for p in found]) + " |\n"
            res += "| --- | " + " | ".join(["---"] * len(found)) + " |\n"
            res += "| **Score** | " + " | ".join([str(p['score']) for p in found]) + " |\n"
            res += "| **Title** | " + " | ".join([str(p['title']) for p in found]) + " |\n"
            res += "| **Company** | " + " | ".join([str(p['company']) for p in found]) + " |\n"
            res += "| **YoE** | " + " | ".join([f"{p['yoe']} yrs" for p in found]) + " |\n"
            res += "| **Notice Period** | " + " | ".join([f"{p['notice']} days" for p in found]) + " |\n\n"
            
            res += "**Comparative Analysis:**\n"
            p1, p2 = found[0], found[1]
            if float(p1["score"]) > float(p2["score"]):
                res += f"- **{p1['name']}** is ranked higher (Score: {p1['score']}) mainly due to alignment with core experience bands or product company background.\n"
            else:
                res += f"- **{p2['name']}** is ranked higher (Score: {p2['score']}) due to superior technical depth or availability signals.\n"
            return res

    # 2. Email drafting query
    if "email" in msg_lower or "outreach" in msg_lower or "draft" in msg_lower:
        cand = None
        for c in candidates:
            p = c.get("details", {}).get("profile", {})
            name = p.get("anonymized_name", f"Candidate {c['candidate_id']}")
            cid = c["candidate_id"]
            if cid.lower() in msg_lower or name.lower() in msg_lower or f"#{c['rank']}" in msg_lower:
                skills_list = [s.get("name", "") for s in c.get("details", {}).get("skills", [])]
                cand = {
                    "id": cid,
                    "name": name,
                    "rank": c["rank"],
                    "title": p.get("current_title", "Software Engineer"),
                    "company": p.get("current_company", "Top Tech Company"),
                    "yoe": p.get("years_of_experience", 5),
                    "skills": skills_list if skills_list else ["Python", "AI", "Machine Learning"],
                    "notice": c.get("details", {}).get("redrob_signals", {}).get("notice_period_days", 30),
                    "github": c.get("details", {}).get("redrob_signals", {}).get("github_activity_score", -1)
                }
                break
                
        if not cand and len(candidates) > 0:
            c = candidates[0]
            p = c.get("details", {}).get("profile", {})
            skills_list = [s.get("name", "") for s in c.get("details", {}).get("skills", [])]
            cand = {
                "id": c["candidate_id"],
                "name": p.get("anonymized_name", "Top Candidate"),
                "rank": 1,
                "title": p.get("current_title", "Software Engineer"),
                "company": p.get("current_company", "Top Tech Company"),
                "yoe": p.get("years_of_experience", 5),
                "skills": skills_list if skills_list else ["Python", "AI"],
                "notice": c.get("details", {}).get("redrob_signals", {}).get("notice_period_days", 30),
                "github": c.get("details", {}).get("redrob_signals", {}).get("github_activity_score", -1)
            }
            
        if cand:
            email = f"**Subject:** Exciting Founding Team Opportunity - Senior AI Engineer at AI-Screening Enginee\n\n"
            email += f"Hi {cand['name']},\n\n"
            email += f"I hope this message finds you well.\n\n"
            email += f"I was reviewing your impressive background, particularly your tenure as a **{cand['title']}** at **{cand['company']}** and your {cand['yoe']} years of experience. We are currently building a founding AI team, and your expertise in **{', '.join(cand['skills'][:3])}** aligns exceptionally well with our technical challenges.\n\n"
            if cand['github'] > 40:
                email += f"I also noticed your strong contributions on GitHub (Activity Score: {cand['github']}), which represents the high-signal builder mindset we value.\n\n"
            email += f"Since your notice period is {cand['notice']} days, we would love to connect for a quick 15-minute conversation to explore if there is mutual alignment.\n\n"
            email += "Are you free for a call sometime this week?\n\n"
            email += "Best regards,\n[Recruiter Name]\nAI-Screening Enginee Talent Intelligence"
            return f"Here is a personalized outreach email draft for **{cand['name']}** (Rank #{cand['rank']}):\n\n---\n\n{email}"

    # 3. Skills query
    skills_query = []
    for kw in ["python", "pytorch", "embeddings", "vector", "faiss", "pinecone", "weaviate", "qdrant", "milvus", "rag", "sql", "java", "nlp"]:
        if kw in msg_lower:
            skills_query.append(kw)
            
    if skills_query:
        matching = []
        for c in candidates:
            skills = [s.get("name", "").lower() for s in c.get("details", {}).get("skills", [])]
            if any(sq in s for sq in skills_query for s in skills):
                p = c.get("details", {}).get("profile", {})
                matching.append({
                    "name": p.get("anonymized_name", f"Candidate {c['candidate_id']}"),
                    "rank": c["rank"],
                    "score": f"{c['score']:.4f}",
                    "skills": skills
                })
                
        if matching:
            res = f"### Candidates with expertise in **{', '.join(skills_query)}**:\n\n"
            for m in matching[:5]:
                res += f"- **#{m['rank']} - {m['name']}** (Score: {m['score']}): Knows {', '.join([s for s in m['skills'] if any(sq in s.lower() for sq in skills_query)])}\n"
            return res

    # 4. Notice period query
    if "notice" in msg_lower or "available" in msg_lower or "immediate" in msg_lower:
        matching = []
        for c in candidates:
            notice = c.get("details", {}).get("redrob_signals", {}).get("notice_period_days", 90)
            if notice <= 30:
                p = c.get("details", {}).get("profile", {})
                matching.append({
                    "name": p.get("anonymized_name", f"Candidate {c['candidate_id']}"),
                    "rank": c["rank"],
                    "score": f"{c['score']:.4f}",
                    "notice": notice
                })
        if matching:
            res = "### Immediate / Low Notice Candidates (<= 30 days):\n\n"
            for m in matching[:5]:
                res += f"- **#{m['rank']} - {m['name']}**: {m['notice']} Days notice period (Score: {m['score']})\n"
            return res

    # 5. GitHub / Open source query
    if "github" in msg_lower or "open source" in msg_lower or "code" in msg_lower:
        matching = []
        for c in candidates:
            git = c.get("details", {}).get("redrob_signals", {}).get("github_activity_score", -1)
            if git > 40:
                p = c.get("details", {}).get("profile", {})
                matching.append({
                    "name": p.get("anonymized_name", f"Candidate {c['candidate_id']}"),
                    "rank": c["rank"],
                    "score": f"{c['score']:.4f}",
                    "github": git
                })
        if matching:
            res = "### Candidates with High GitHub Contribution Scores:\n\n"
            for m in matching[:5]:
                res += f"- **#{m['rank']} - {m['name']}**: GitHub Activity Score of **{m['github']}** (Score: {m['score']})\n"
            return res

    # 6. Specific candidate query
    for c in candidates:
        p = c.get("details", {}).get("profile", {})
        name = p.get("anonymized_name", f"Candidate {c['candidate_id']}")
        cid = c["candidate_id"]
        if cid.lower() in msg_lower or name.lower() in msg_lower or f"#{c['rank']}" in msg_lower:
            cand = c
            why = cand.get("why_cards", {})
            res = f"### Profile Fit Analysis: {name} (Rank #{cand['rank']})\n\n"
            res += f"- **Match Score:** `{cand['score']:.4f}` ({Math.round(cand.get('confidence_score', cand['score']*100))}% Confidence)\n"
            res += f"- **Current Role:** {p.get('current_title', 'N/A')} at {p.get('current_company', 'N/A')}\n"
            res += f"- **Experience:** {p.get('years_of_experience', 0)} years\n\n"
            if why.get("pros"):
                res += "**Key Strengths:**\n" + "\n".join([f"  + {pro}" for pro in why["pros"]]) + "\n\n"
            if why.get("cons"):
                res += "**Risk Factors:**\n" + "\n".join([f"  - {con}" for con in why["cons"]]) + "\n\n"
            res += f"**Automated Fit Summary:** {cand.get('reasoning', 'No summary available.')}"
            return res

    # Generic Assistant overview response
    top3 = []
    for c in candidates[:3]:
        p = c.get("details", {}).get("profile", {})
        top3.append(f"#{c['rank']} {p.get('anonymized_name', c['candidate_id'])} ({p.get('current_title', 'Engineer')})")
        
    return (
        f"I've analyzed the shortlisted candidate pool for this role. "
        f"The top candidates are currently **{', '.join(top3)}**.\n\n"
        "You can ask me to:\n"
        "1. **Compare candidates** (e.g., *'Compare Candidate #1 and Candidate #3'*)\n"
        "2. **Filter by skills** (e.g., *'Who has experience with PyTorch and FAISS?'*)\n"
        "3. **Draft personalized outreach emails** (e.g., *'Draft an email for #1 candidate'*)\n"
        "4. **Analyze risk factors** (e.g., *'Show low notice period candidates'*)"
    )

@app.post("/api/chat")
async def chat_assistant(
    request: ChatMessage,
    username: str = Depends(get_current_user),
    x_gemini_key: Optional[str] = Header(None)
):
    try:
        cand_res = get_ranked_candidates(request.role_id, username)
        candidates = cand_res.get("candidates", [])
        
        jd_res = get_job_description(request.role_id, username)
        jd_text = jd_res.get("job_description", "")
        
        api_key = x_gemini_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            fallback_text = get_fallback_bot_response(request.message, jd_text, candidates)
            return {"status": "success", "response": fallback_text, "engine": "local_heuristics"}
            
        cand_summary_list = []
        for c in candidates[:15]:
            p = c.get("details", {}).get("profile", {})
            skills = [s.get("name", "") for s in c.get("details", {}).get("skills", [])]
            cand_summary_list.append(
                f"Rank #{c['rank']} (Score: {c['score']:.4f}) - Candidate ID: {c['candidate_id']}\n"
                f"Name: {p.get('anonymized_name', 'Unknown')}\n"
                f"Headline: {p.get('headline', '')}\n"
                f"YoE: {p.get('years_of_experience', 0)}\n"
                f"Company: {p.get('current_company', '')}\n"
                f"Skills: {', '.join(skills[:8])}\n"
                f"Notice Period: {c.get('details', {}).get('redrob_signals', {}).get('notice_period_days', 60)} days\n"
                f"Reasoning: {c.get('reasoning', '')}\n"
            )
            
        candidates_context = "\n---\n".join(cand_summary_list)
        
        system_prompt = (
            "You are an advanced AI Recruiter Assistant integrated inside AI-Screening Enginee Talent Intelligence dashboard.\n"
            "You help recruitment teams query, compare, shortlist, analyze, and draft outreach emails for candidates.\n\n"
            f"ACTIVE TARGET JOB DESCRIPTION:\n{jd_text}\n\n"
            f"SHORTLISTED CANDIDATES (TOP 15):\n{candidates_context}\n\n"
            "INSTRUCTIONS:\n"
            "1. Base your answers strictly on the candidates list and JD provided above.\n"
            "2. If requested to draft outreach emails, make them highly personalized, professional, and highlight candidate's specific current title, company, skills, notice period, and GitHub activity score.\n"
            "3. If compared, build a markdown table highlighting metrics.\n"
            "4. Be clear, concise, and professional."
        )
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": system_prompt + f"\n\nUSER QUESTION: {request.message}"}]}
            ]
        }
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return {"status": "success", "response": text, "engine": "gemini_llm"}
            else:
                fallback_text = get_fallback_bot_response(request.message, jd_text, candidates)
                return {"status": "success", "response": fallback_text, "engine": "local_fallback"}
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
