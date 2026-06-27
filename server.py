import os
import json
import csv
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any

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

# Cache candidates data in memory for fast retrieval (only Top 100/sample, or stream from JSONL)
def load_candidate_by_id(candidate_id: str) -> Dict[str, Any]:
    custom_candidates_file = os.path.join(WORKSPACE_DIR, "candidates_custom.jsonl")
    if os.path.exists(custom_candidates_file):
        candidates_file = custom_candidates_file
    else:
        candidates_file = os.path.join(DATASET_DIR, "candidates.jsonl")
        
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

@app.get("/api/job-description")
def get_job_description():
    custom_jd_path = os.path.join(WORKSPACE_DIR, "job_description_custom.txt")
    if os.path.exists(custom_jd_path):
        jd_path = custom_jd_path
    else:
        jd_path = os.path.join(DATASET_DIR, "job_description.txt")
        
    if not os.path.exists(jd_path):
        return {"content": "Job description file not found."}
        
    try:
        with open(jd_path, "r", encoding="utf-8") as f:
            text = f.read()
        return {"content": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/candidates")
def get_ranked_candidates():
    # Attempt to read from the final submission.csv (fall back to sample if not generated yet)
    submission_path = os.path.join(WORKSPACE_DIR, "team_submission.csv")
    if not os.path.exists(submission_path):
        submission_path = os.path.join(WORKSPACE_DIR, "team_submission_sample.csv")
        
    if not os.path.exists(submission_path):
        return {"status": "error", "message": "No submission CSV files found. Please run the ranker first."}
        
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
        # To avoid reading 487MB sequentially 100 times, we read candidates.jsonl in a single pass 
        # and match the candidate IDs! This is extremely fast (< 3 seconds)
        cids_to_find = {item["candidate_id"] for item in top_candidates}
        matched_profiles = {}
        
        custom_candidates_file = os.path.join(WORKSPACE_DIR, "candidates_custom.jsonl")
        if os.path.exists(custom_candidates_file):
            candidates_file = custom_candidates_file
        else:
            candidates_file = os.path.join(DATASET_DIR, "candidates.jsonl")
            
        if os.path.exists(candidates_file):
            with open(candidates_file, "r", encoding="utf-8-sig") as f:
                for line in f:
                    if not line.strip():
                        continue
                    # Quick pre-filter check
                    if any(cid in line for cid in cids_to_find):
                        cand = json.loads(line)
                        if cand["candidate_id"] in cids_to_find:
                            matched_profiles[cand["candidate_id"]] = cand
                            
        # Merge profile details back into our list
        for item in top_candidates:
            cid = item["candidate_id"]
            if cid in matched_profiles:
                item["details"] = matched_profiles[cid]
            else:
                item["details"] = {"candidate_id": cid, "profile": {"anonymized_name": "Unknown", "headline": "Unavailable"}}
                
        return {"status": "success", "candidates": top_candidates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/candidate/{candidate_id}")
def get_candidate_details(candidate_id: str):
    try:
        cand = load_candidate_by_id(candidate_id)
        if not cand:
            raise HTTPException(status_code=404, detail="Candidate not found")
        return cand
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/rank")
def trigger_ranking():
    import subprocess
    try:
        custom_candidates_file = os.path.join(WORKSPACE_DIR, "candidates_custom.jsonl")
        if os.path.exists(custom_candidates_file):
            candidates_file = custom_candidates_file
        else:
            candidates_file = os.path.join(DATASET_DIR, "candidates.jsonl")
            
        out_file = os.path.join(WORKSPACE_DIR, "team_submission.csv")
        custom_jd_path = os.path.join(WORKSPACE_DIR, "job_description_custom.txt")
        
        # Execute rank.py using subprocess
        cmd = [
            "uv", "run", "python", "rank.py",
            "--candidates", candidates_file,
            "--out", out_file
        ]
        if os.path.exists(custom_jd_path):
            cmd.extend(["--jd", custom_jd_path])
            
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return {"status": "success", "message": "Ranking calculated successfully."}
    except Exception as e:
        # Check stderr of the failed run if available
        stderr = getattr(e, "stderr", "")
        raise HTTPException(status_code=500, detail=f"Ranking execution failed: {str(e)}. Stderr: {stderr}")

@app.get("/api/status")
def get_status():
    custom_jd_path = os.path.join(WORKSPACE_DIR, "job_description_custom.txt")
    custom_candidates_path = os.path.join(WORKSPACE_DIR, "candidates_custom.jsonl")
    
    has_custom_jd = os.path.exists(custom_jd_path)
    has_custom_candidates = os.path.exists(custom_candidates_path)
    
    candidates_count = 0
    if has_custom_candidates:
        try:
            with open(custom_candidates_path, "r", encoding="utf-8-sig") as f:
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

@app.post("/api/job-description")
def update_job_description(jd: JobDescriptionUpdate):
    try:
        custom_jd_path = os.path.join(WORKSPACE_DIR, "job_description_custom.txt")
        with open(custom_jd_path, "w", encoding="utf-8") as f:
            f.write(jd.content)
        return {"status": "success", "message": "Job description updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def convert_csv_to_jsonl(csv_content: str, output_path: str) -> int:
    import io
    import csv
    
    reader = csv.DictReader(io.StringIO(csv_content))
    fieldnames = reader.fieldnames or []
    # Normalize header names: lowercase, strip, remove underscores
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
def upload_candidates(file: UploadFile = File(...)):
    if not (file.filename.endswith(".jsonl") or file.filename.endswith(".csv")):
        raise HTTPException(status_code=400, detail="Only .jsonl or .csv files are allowed.")
        
    try:
        custom_candidates_path = os.path.join(WORKSPACE_DIR, "candidates_custom.jsonl")
        
        if file.filename.endswith(".jsonl"):
            with open(custom_candidates_path, "wb") as f:
                while content := file.file.read(1024 * 1024):
                    f.write(content)
            return {"status": "success", "message": "Candidates pool JSONL uploaded successfully."}
        else:
            content_bytes = file.file.read()
            try:
                content_str = content_bytes.decode("utf-8-sig")
            except UnicodeDecodeError:
                content_str = content_bytes.decode("latin-1")
                
            count = convert_csv_to_jsonl(content_str, custom_candidates_path)
            return {
                "status": "success",
                "message": f"Successfully parsed and converted CSV. Loaded {count} candidates."
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/reset")
def reset_workspace():
    custom_jd_path = os.path.join(WORKSPACE_DIR, "job_description_custom.txt")
    custom_candidates_path = os.path.join(WORKSPACE_DIR, "candidates_custom.jsonl")
    
    try:
        if os.path.exists(custom_jd_path):
            os.remove(custom_jd_path)
        if os.path.exists(custom_candidates_path):
            os.remove(custom_candidates_path)
        
        # Also clean up calculated ranks CSV if present
        submission_path = os.path.join(WORKSPACE_DIR, "team_submission.csv")
        if os.path.exists(submission_path):
            os.remove(submission_path)
            
        return {"status": "success", "message": "Workspace reset to default dataset successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Serves build frontend assets if compiled
frontend_dist = os.path.join(WORKSPACE_DIR, "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host=host, port=port)
