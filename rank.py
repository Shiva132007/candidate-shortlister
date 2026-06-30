import os
import json
import argparse
import numpy as np
import csv
import re
import httpx
from datetime import datetime
from sentence_transformers import SentenceTransformer

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))

# Redirect HF cache to project workspace to avoid permission issues
os.environ["HF_HOME"] = os.path.join(WORKSPACE_DIR, ".hf_cache")

def get_job_description_query(jd_path=None):
    if jd_path and os.path.exists(jd_path):
        try:
            with open(jd_path, "r", encoding="utf-8") as f:
                text = f.read().strip()
            if text:
                return text
        except Exception as e:
            print(f"Warning: failed to read custom JD: {e}")

    # Dense query summarizing key JD requirements for embeddings-based similarity
    return (
        "Senior AI Engineer Founding Team applied ML embeddings-based retrieval systems "
        "sentence-transformers vector databases Pinecone Weaviate Qdrant Milvus FAISS "
        "hybrid search Python ranking systems evaluation frameworks NDCG MRR MAP learning-to-rank "
        "LLM fine-tuning LoRA QLoRA PEFT"
    )

def is_technical_profile(cand):
    # Filters out keyword stuffers who have never held a technical/developer/engineer role
    history = cand.get("career_history", [])
    profile = cand.get("profile", {})
    
    headline_lower = profile.get("headline", "").lower()
    current_title_lower = profile.get("current_title", "").lower()
    
    # Non-tech keywords that represent stuffers if they dominate the history
    banned_roles = ["hr manager", "hr specialist", "recruiter", "human resources",
                    "accountant", "bookkeeper", "finance specialist", "finance manager",
                    "sales executive", "sales manager", "marketing manager", "marketing specialist",
                    "content writer", "copywriter", "graphic designer", "brand designer",
                    "customer support", "support specialist"]
    
    # If their current title is a banned non-tech role and they have no tech history
    current_is_banned = any(role in current_title_lower for role in banned_roles)
    
    # Check if they have at least one technical job in their career history
    tech_keywords = ["engineer", "developer", "scientist", "architect", "programmer", 
                     "coder", "tech lead", "technical lead", "cto", "data analyst", "product manager"]
    
    has_tech_job = False
    for job in history:
        title = job.get("title", "").lower()
        if any(kw in title for kw in tech_keywords):
            # Double check it's not a false match like "hr engineer" or similar
            if not any(br in title for br in banned_roles):
                has_tech_job = True
                break
                
    if current_is_banned and not has_tech_job:
        return False
        
    return True

def analyze_pedigree(cand):
    # Determines if the candidate has product experience or only consulting
    history = cand.get("career_history", [])
    
    consulting_firms = ["tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini", 
                        "tech mahindra", "mphasis", "mindtree", "hcl", "genpact"]
                        
    product_firms = ["hooli", "pied piper", "wayne enterprises", "stark industries", "initech", 
                     "globex inc", "tyrell corp", "cyberdyne systems", "acme corp", "razorpay", 
                     "cred", "flipkart", "zomato", "swiggy", "paytm", "meesho", "nykaa", 
                     "freshworks", "ola", "phonepe", "unacademy", "vedantu"]
                     
    companies = [job.get("company", "").lower() for job in history if job.get("company")]
    
    if not companies:
        return "neutral"
        
    # Check if all their companies are consulting firms
    all_consulting = all(any(cf in comp for cf in consulting_firms) for comp in companies)
    if all_consulting:
        return "only_consulting"
        
    # Check if they have product company experience
    has_product = any(any(pf in comp for pf in product_firms) for comp in companies)
    if has_product:
        return "has_product"
        
    return "neutral"

def get_location_multiplier(profile):
    # Score based on hybrid travel/relocation preference
    loc = profile.get("location", "").lower()
    country = profile.get("country", "").lower()
    
    preferred_cities = ["pune", "noida", "delhi", "ncr", "gurgaon", "ghaziabad", "faridabad"]
    other_tech_hubs = ["hyderabad", "mumbai", "bangalore", "bengaluru", "chennai"]
    
    if any(city in loc for city in preferred_cities):
        return 1.10 # Preferred local
    elif any(city in loc for city in other_tech_hubs):
        return 0.95 # Welcome hub
    elif country == "india" or "india" in loc:
        return 0.75 # Relocation candidate
    else:
        return 0.25 # International (requires visa, not sponsored)

def get_notice_period_multiplier(signals):
    # Score based on notice period (sub-30 days preferred)
    notice = signals.get("notice_period_days", 60)
    if notice <= 30:
        return 1.10
    elif notice <= 60:
        return 0.95
    elif notice <= 90:
        return 0.80
    else:
        return 0.40 # Binds notice buyout limits

def compile_text_profile(cand):
    # Text compilation function identical to embedding script for consistency
    profile = cand.get("profile", {})
    skills = cand.get("skills", [])
    history = cand.get("career_history", [])
    
    parts = []
    headline = profile.get("headline", "")
    current_title = profile.get("current_title", "")
    parts.append(f"Title: {current_title}")
    parts.append(f"Headline: {headline}")
    
    summary = profile.get("summary", "")
    if summary:
        parts.append(f"Summary: {summary}")
        
    if skills:
        skill_list = [s.get("name", "") for s in skills if s.get("name")]
        parts.append(f"Skills: {', '.join(skill_list)}")
        
    if history:
        history_parts = []
        for job in history[:4]:
            comp = job.get("company", "")
            title = job.get("title", "")
            duration = job.get("duration_months", 0)
            desc = job.get("description", "")
            job_str = f"- {title} at {comp} ({duration} mos)"
            if desc:
                job_str += f": {desc}"
            history_parts.append(job_str)
        parts.append("Experience:\n" + "\n".join(history_parts))
        
    return "\n".join(parts)

def detect_honeypot_runtime(cand):
    """
    Returns (is_honeypot, reason) if any fraud or timeline anomaly is detected dynamically.
    """
    profile = cand.get("profile", {})
    history = cand.get("career_history", [])
    education = cand.get("education", [])
    skills = [s.get("name", "").lower() for s in cand.get("skills", [])]
    
    # 1. Academic Timeline Mismatch
    grad_years = []
    for edu in education:
        end_yr = edu.get("end_year")
        if end_yr and isinstance(end_yr, int):
            grad_years.append(end_yr)
        elif end_yr and isinstance(end_yr, str) and end_yr.isdigit():
            grad_years.append(int(end_yr))
            
    if grad_years:
        earliest_grad_year = min(grad_years)
        senior_keywords = ["senior", "lead", "architect", "manager", "director", "head", "cto", "vp", "president", "principal"]
        for job in history:
            title = job.get("title", "").lower()
            start_date = job.get("start_date", "")
            if start_date:
                try:
                    start_year = int(start_date.split("-")[0])
                    # Flag senior roles held more than 1 year prior to college graduation
                    if any(sk in title for sk in senior_keywords) and start_year < (earliest_grad_year - 1):
                        if not any(x in title for x in ["student", "representative", "volunteer", "intern", "trainee", "freshman"]):
                            return True, f"Timeline Anomaly: Held senior role '{job.get('title')}' at {job.get('company')} in {start_year} before graduation in {earliest_grad_year}"
                except Exception:
                    pass

    # 2. Overlapping Positions
    parsed_jobs = []
    for job in history:
        company = job.get("company", "").lower()
        title = job.get("title", "").lower()
        if any(x in title or x in company for x in ["intern", "freelance", "contractor", "volunteer", "student"]):
            continue
        s_date = job.get("start_date")
        e_date = job.get("end_date")
        try:
            if s_date:
                s_dt = datetime.strptime(s_date, "%Y-%m-%d")
                if e_date:
                    e_dt = datetime.strptime(e_date, "%Y-%m-%d")
                else:
                    e_dt = datetime(2026, 6, 27)
                parsed_jobs.append((s_dt, e_dt, job.get("company")))
        except Exception:
            pass
            
    for i in range(len(parsed_jobs)):
        for j in range(i + 1, len(parsed_jobs)):
            s1, e1, c1 = parsed_jobs[i]
            s2, e2, c2 = parsed_jobs[j]
            if c1 == c2 or not c1 or not c2:
                continue
            latest_start = max(s1, s2)
            earliest_end = min(e1, e2)
            if latest_start < earliest_end:
                overlap_days = (earliest_end - latest_start).days
                if overlap_days > 180:
                    return True, f"Timeline Anomaly: Impossible overlap of {overlap_days // 30} months in full-time roles at {c1} and {c2}"

    # 3. Keyword Stuffing without Tech Tenure
    headline_lower = profile.get("headline", "").lower()
    current_title_lower = profile.get("current_title", "").lower()
    banned_roles = ["hr manager", "hr specialist", "recruiter", "human resources",
                    "accountant", "bookkeeper", "finance specialist", "finance manager",
                    "sales executive", "sales manager", "marketing manager", "marketing specialist",
                    "content writer", "copywriter", "graphic designer", "brand designer",
                    "customer support", "support specialist", "operations manager"]
    
    current_is_banned = any(role in current_title_lower or role in headline_lower for role in banned_roles)
    
    tech_keywords = ["engineer", "developer", "scientist", "architect", "programmer", 
                     "coder", "tech lead", "technical lead", "cto", "data analyst", "product manager"]
    has_tech_job = False
    for job in history:
        title = job.get("title", "").lower()
        if any(kw in title for kw in tech_keywords):
            if not any(br in title for br in banned_roles):
                has_tech_job = True
                break
                
    ml_keywords = ["pytorch", "tensorflow", "rag", "fine-tuning", "lora", "embeddings", "milvus", "weaviate", "qdrant", "vector database", "sentence-transformers"]
    stuffed_skills = [s for s in skills if any(mk in s for mk in ml_keywords)]
    
    if current_is_banned and not has_tech_job and len(stuffed_skills) >= 2:
        return True, f"Fraud Alert: Operations/non-tech role ('{profile.get('current_title')}') with zero technical tenure listing advanced skills ({', '.join(stuffed_skills)})"
        
    return False, ""

def parse_job_description(jd_text, api_key=None):
    if api_key:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        prompt = (
            "You are an expert technical recruiter. Parse the following Job Description into a clean JSON structure.\n\n"
            "JOB DESCRIPTION:\n"
            f"{jd_text}\n\n"
            "Return ONLY a JSON object (no markdown, no backticks, no other text) with the following structure:\n"
            "{\n"
            "  \"title\": \"Exact job title\",\n"
            "  \"experience_min\": 5,\n"
            "  \"experience_max\": 9,\n"
            "  \"tech_skills\": [\"python\", \"pytorch\", ...],\n"
            "  \"ir_skills\": [\"embeddings\", \"vector database\", ...],\n"
            "  \"behavioral_priorities\": [\"github activity\", ...]\n"
            "}"
        )
        try:
            res = httpx.post(url, json={
                "contents": [{"parts": [{"text": prompt}]}]
            }, timeout=10.0)
            if res.status_code == 200:
                text_res = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                if text_res.startswith("```"):
                    text_res = text_res.split("```")[1]
                    if text_res.startswith("json"):
                        text_res = text_res[4:]
                return json.loads(text_res.strip())
        except Exception as e:
            print(f"Warning: Gemini JD parser failed: {e}. Falling back to rule-based parser.")
            
    # Local Fallback
    jd_lower = jd_text.lower()
    title = "Senior AI Engineer"
    for line in jd_text.split("\n"):
        if "title:" in line.lower() or "role:" in line.lower() or "position:" in line.lower():
            title = line.split(":")[-1].strip()
            break
        elif "engineer" in line.lower() or "developer" in line.lower():
            if len(line.strip()) < 55:
                title = line.strip()
                break
                
    exp_min, exp_max = 5, 9
    yoe_matches = re.findall(r'(\d+)\s*[-to]+\s*(\d+)\s*(?:years|yoe)', jd_lower)
    if yoe_matches:
        try:
            exp_min, exp_max = int(yoe_matches[0][0]), int(yoe_matches[0][1])
        except Exception:
            pass
            
    tech_candidates = ["python", "pytorch", "tensorflow", "scikit-learn", "numpy", "pandas", "fastapi", "django", "flask", "docker", "kubernetes", "aws", "gcp"]
    tech_skills = [t for t in tech_candidates if t in jd_lower]
    if not tech_skills:
        tech_skills = ["python", "pytorch"]
        
    ir_candidates = ["embeddings", "vector database", "pinecone", "weaviate", "qdrant", "milvus", "faiss", "hybrid search", "rag", "retrieval", "semantic search", "ndcg", "mrr", "map", "learning-to-rank"]
    ir_skills = [c for c in ir_candidates if c in jd_lower]
    if not ir_skills:
        ir_skills = ["embeddings", "vector database", "rag"]
        
    behavioral = []
    if "github" in jd_lower:
        behavioral.append("github contributions")
    if "notice" in jd_lower or "availability" in jd_lower:
        behavioral.append("immediate availability")
    if "active" in jd_lower or "response" in jd_lower:
        behavioral.append("high response rate")
    if not behavioral:
        behavioral = ["immediate availability", "high response rate"]
        
    return {
        "title": title,
        "experience_min": exp_min,
        "experience_max": exp_max,
        "tech_skills": tech_skills,
        "ir_skills": ir_skills,
        "behavioral_priorities": behavioral
    }

def generate_llm_reasoning_batch(top_candidates, jd_text, api_key):
    cand_details_list = []
    for cand in top_candidates:
        c_id = cand["candidate_id"]
        profile = cand["record"].get("profile", {})
        skills = ", ".join([s.get("name", "") for s in cand["record"].get("skills", [])])
        signals = cand["record"].get("redrob_signals", {})
        cand_details_list.append(
            f"Candidate ID: {c_id}\n"
            f"Current Title: {profile.get('current_title')} at {profile.get('current_company')}\n"
            f"YoE: {profile.get('years_of_experience')} years\n"
            f"Skills: {skills}\n"
            f"Notice Period: {signals.get('notice_period_days')} days | Response Rate: {int(signals.get('recruiter_response_rate', 0)*100)}%\n"
        )
    candidates_context = "\n---\n".join(cand_details_list)
    prompt = (
        "You are an expert technical recruiter analyzing candidates for a job role.\n\n"
        f"JOB ROLE DESCRIPTION:\n{jd_text}\n\n"
        f"TOP RANKED CANDIDATES:\n{candidates_context}\n\n"
        "INSTRUCTIONS:\n"
        "Generate a highly specific, professional 2-sentence match justification for each of the candidates listed above.\n"
        "Highlight their experience, pedigree alignment, core skills, and note any availability or relocation constraints if relevant.\n"
        "Keep the tone professional and fact-based.\n"
        "Return ONLY a JSON object (no markdown, no backticks, no other text) mapping each candidate_id to their reasoning text, like this:\n"
        "{\n"
        "  \"CAND_0000001\": \"Exceptional candidate with 7 years of ML experience. Has strong vector search skills and product pedigree, but has a 60-day notice period.\",\n"
        "  ...\n"
        "}"
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    try:
        res = httpx.post(url, json={
            "contents": [{"parts": [{"text": prompt}]}]
        }, timeout=25.0)
        if res.status_code == 200:
            text_res = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if text_res.startswith("```"):
                text_res = text_res.split("```")[1]
                if text_res.startswith("json"):
                    text_res = text_res[4:]
            return json.loads(text_res.strip())
    except Exception as e:
        print(f"Warning: Gemini batch reasoning failed: {e}. Falling back to local reasoning.")
    return {}

def generate_reasoning_improved(cand, parsed_jd, skill_gap, pedigree):
    profile = cand.get("profile", {})
    history = cand.get("career_history", [])
    signals = cand.get("redrob_signals", {})
    
    yoe = profile.get("years_of_experience", 0)
    current_title = profile.get("current_title", "Engineer")
    last_company = history[0].get("company", "previous employer") if history else "previous employer"
    notice = signals.get("notice_period_days", 30)
    
    intro = f"Candidate is a {current_title} with {yoe} years of experience, recently at {last_company}."
    
    matching = skill_gap.get("matching", [])
    if matching:
        tech_clause = f"Demonstrates core competency in {', '.join(matching[:3])}."
    else:
        tech_clause = "Possesses solid engineering fundamentals, looking to expand their technical stack."
        
    if pedigree == "has_product":
        pedigree_clause = f"Brings high-value product pedigree from history with {last_company}."
    elif pedigree == "only_consulting":
        pedigree_clause = "Experience is concentrated in consulting-only services."
    else:
        pedigree_clause = f"Shows a stable career trajectory at {last_company}."
        
    resp_rate = int(signals.get("recruiter_response_rate", 0) * 100)
    signal_clause = f"Active with a {resp_rate}% response rate and {notice}-day notice availability."
    
    return f"{intro} {tech_clause} {pedigree_clause} {signal_clause}"

def generate_reasoning(cand, rank):
    # Backward compatible fallback wrapper
    return generate_reasoning_improved(cand, {}, {"matching": []}, "neutral")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=str, required=True, help="Path to candidates.jsonl")
    parser.add_argument("--out", type=str, required=True, help="Path to output submission CSV")
    parser.add_argument("--jd", type=str, default=None, help="Path to job description text file")
    args = parser.parse_args()
    
    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    
    # 1. Load Blacklists
    blacklist = set()
    
    # Try loading pre-calculated honeypots lists
    for filename in ["all_detected_honeypots.json", "honeypots.json", "undergrad_anomalies.json"]:
        path = os.path.join(WORKSPACE_DIR, filename)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        blacklist.update(data.keys())
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and "candidate_id" in item:
                                blacklist.add(item["candidate_id"])
                            elif isinstance(item, str):
                                blacklist.add(item)
            except Exception as e:
                print(f"Warning: failed to load blacklist {filename}: {e}")
                
    print(f"Loaded blacklist. Total blacklisted candidate IDs: {len(blacklist)}")
    
    # 2. Try loading precomputed embeddings and ID map
    emb_path = os.path.join(WORKSPACE_DIR, "embeddings.npy")
    map_path = os.path.join(WORKSPACE_DIR, "candidate_id_map.json")
    
    precomputed_embeddings = None
    candidate_id_map = {}
    
    if os.path.exists(emb_path) and os.path.exists(map_path):
        try:
            precomputed_embeddings = np.load(emb_path)
            with open(map_path, "r", encoding="utf-8") as f:
                candidate_id_map = json.load(f)
            print(f"Loaded precomputed embeddings: Shape {precomputed_embeddings.shape}")
        except Exception as e:
            print(f"Warning: failed to load precomputed embeddings: {e}")
            
    # Fallback to sample embeddings if full ones aren't generated yet (useful for debugging/testing)
    if precomputed_embeddings is None:
        emb_path_sample = os.path.join(WORKSPACE_DIR, "embeddings_sample.npy")
        map_path_sample = os.path.join(WORKSPACE_DIR, "candidate_id_map_sample.json")
        if os.path.exists(emb_path_sample) and os.path.exists(map_path_sample):
            try:
                precomputed_embeddings = np.load(emb_path_sample)
                with open(map_path_sample, "r", encoding="utf-8") as f:
                    candidate_id_map = json.load(f)
                print(f"Loaded fallback SAMPLE embeddings: Shape {precomputed_embeddings.shape}")
            except Exception as e:
                print(f"Warning: failed to load sample embeddings: {e}")
                
    # 3. Load SentenceTransformer model locally (if we need to encode on the fly)
    model = None
    model_path = os.path.join(WORKSPACE_DIR, "model", "all-MiniLM-L6-v2")
    
    # Encode Query
    query_text = get_job_description_query(args.jd)
    query_vector = None
    
    if os.path.exists(model_path):
        try:
            model = SentenceTransformer(model_path, local_files_only=True)
            query_vector = model.encode(query_text, normalize_embeddings=True)
            print("Successfully loaded model locally and encoded JD query.")
        except Exception as e:
            print(f"Warning: failed to load model locally: {e}")
            
    if query_vector is None:
        # Emergency backup: construct a fake normalized query vector if model fails to load
        query_vector = np.ones((384,), dtype=np.float32) / np.sqrt(384)
        print("Warning: constructed fallback query vector.")
        
    # 4. Parse JD requirements
    api_key = os.environ.get("GEMINI_API_KEY")
    
    # Load raw JD content
    jd_content = ""
    if args.jd and os.path.exists(args.jd):
        try:
            with open(args.jd, "r", encoding="utf-8") as f:
                jd_content = f.read().strip()
        except Exception:
            pass
            
    parsed_jd = parse_job_description(jd_content or query_text, api_key)
    
    # Cache parsed JD in the role directory
    if args.jd:
        parsed_jd_path = os.path.join(os.path.dirname(args.jd), "job_description_parsed.json")
        try:
            with open(parsed_jd_path, "w", encoding="utf-8") as f:
                json.dump(parsed_jd, f, indent=2)
        except Exception as e:
            print(f"Warning: failed to write parsed JD: {e}")
            
    # 5. Stream Candidates and Compute Scores
    print(f"Processing and scoring candidates from {args.candidates}...")
    tier1_qualified = []
    tier2_fillers = []
    tier3_honeypots = []
    
    with open(args.candidates, "r", encoding="utf-8-sig") as f:
        for line in f:
            if not line.strip():
                continue
            cand = json.loads(line)
            cand_id = cand["candidate_id"]
            
            # Dynamic Runtime Honeypot/Fraud Audit
            is_honeypot_runtime, honeypot_reason = detect_honeypot_runtime(cand)
            is_honeypot = (cand_id in blacklist) or is_honeypot_runtime
            
            is_tech = is_technical_profile(cand)
            pedigree = analyze_pedigree(cand)
            is_consulting_only = pedigree == "only_consulting"
            
            # Semantic score fallback
            cand_vector = None
            if precomputed_embeddings is not None and cand_id in candidate_id_map:
                idx = candidate_id_map[cand_id]
                if idx < len(precomputed_embeddings):
                    cand_vector = precomputed_embeddings[idx]
                    
            if cand_vector is None:
                if model is not None:
                    text_profile = compile_text_profile(cand)
                    cand_vector = model.encode(text_profile, normalize_embeddings=True)
                else:
                    cand_vector = np.zeros((384,), dtype=np.float32)
                    
            semantic_score = float(np.dot(query_vector, cand_vector))
            
            # Heuristics
            profile = cand.get("profile", {})
            signals = cand.get("redrob_signals", {})
            
            # Experience Multiplier
            yoe = profile.get("years_of_experience", 0)
            if yoe < 3:
                exp_mult = 0.10
            elif yoe < 5:
                exp_mult = 0.60
            elif yoe <= 9:
                exp_mult = 1.15 if 6 <= yoe <= 8 else 1.0
            elif yoe <= 12:
                exp_mult = 0.80
            else:
                exp_mult = 0.30
                
            # Pedigree Multiplier
            if pedigree == "has_product":
                ped_mult = 1.15
            elif is_consulting_only:
                ped_mult = 0.10
            elif pedigree == "neutral":
                current_comp = profile.get("current_company", "").lower()
                consulting_firms = ["tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini", "tech mahindra", "mphasis", "mindtree", "hcl", "genpact"]
                if any(cf in current_comp for cf in consulting_firms):
                    ped_mult = 0.85
                else:
                    ped_mult = 1.0
            else:
                ped_mult = 1.0
                
            # Location Multiplier
            loc_mult = get_location_multiplier(profile)
            
            # Notice Period Multiplier
            notice_mult = get_notice_period_multiplier(signals)
            
            # Behavioral Multipliers
            resp_rate = signals.get("recruiter_response_rate", 0.0)
            resp_mult = 0.15 + 0.85 * resp_rate
            
            active_str = signals.get("last_active_date", "")
            active_mult = 1.0
            if active_str:
                try:
                    act_dt = datetime.strptime(active_str, "%Y-%m-%d")
                    curr_dt = datetime(2026, 6, 27)
                    diff_days = (curr_dt - act_dt).days
                    if diff_days > 180:
                        active_mult = 0.40
                    elif diff_days > 90:
                        active_mult = 0.70
                    else:
                        active_mult = 1.05
                except Exception:
                    pass
                    
            open_mult = 1.05 if signals.get("open_to_work_flag", False) else 1.0
            
            git_score = signals.get("github_activity_score", -1)
            if git_score > 50:
                git_mult = 1.10
            elif git_score == -1:
                git_mult = 0.95
            else:
                git_mult = 1.00
                
            ic_rate = signals.get("interview_completion_rate", 0.0)
            if ic_rate >= 0.8:
                ic_mult = 1.05
            elif ic_rate < 0.5:
                ic_mult = 0.70
            else:
                ic_mult = 1.00
                
            multipliers = (exp_mult * ped_mult * loc_mult * notice_mult * 
                           resp_mult * active_mult * open_mult * git_mult * ic_mult)
                           
            final_score = semantic_score * multipliers
            final_score = max(0.0, final_score)
            
            # Calculate requirements scoring breakdown (0-100)
            cand_skills = [s.get("name", "").lower() for s in cand.get("skills", [])]
            required_tech = [s.lower() for s in parsed_jd.get("tech_skills", [])]
            matching_tech = [s for s in required_tech if any(s in cs or cs in s for cs in cand_skills)]
            missing_tech = [s for s in required_tech if s not in matching_tech]
            
            tech_score = 30
            if required_tech:
                tech_score = int((len(matching_tech) / len(required_tech)) * 70 + 30)
                
            required_ir = [s.lower() for s in parsed_jd.get("ir_skills", [])]
            cand_text_lower = compile_text_profile(cand).lower()
            matching_ir = [s for s in required_ir if s in cand_text_lower or any(s in cs for cs in cand_skills)]
            missing_ir = [s for s in required_ir if s not in matching_ir]
            
            ir_score = 30
            if required_ir:
                ir_score = int((len(matching_ir) / len(required_ir)) * 70 + 30)
                
            exp_min = parsed_jd.get("experience_min", 5)
            exp_max = parsed_jd.get("experience_max", 9)
            if exp_min <= yoe <= exp_max:
                exp_score = 100
            elif yoe < exp_min:
                exp_score = max(20, int(100 - (exp_min - yoe) * 20))
            else:
                exp_score = max(30, int(100 - (yoe - exp_max) * 10))
                
            if pedigree == "has_product":
                ped_score = 100
            elif pedigree == "neutral":
                ped_score = 75
            else:
                ped_score = 20
                
            notice_period = signals.get("notice_period_days", 60)
            if notice_period <= 30:
                ns = 100
            elif notice_period <= 60:
                ns = 80
            elif notice_period <= 90:
                ns = 50
            else:
                ns = 20
            rs = int(signals.get("recruiter_response_rate", 0.5) * 100)
            as_score = 70
            if active_str:
                try:
                    act_dt = datetime.strptime(active_str, "%Y-%m-%d")
                    curr_dt = datetime(2026, 6, 27)
                    diff_days = (curr_dt - act_dt).days
                    if diff_days <= 90:
                        as_score = 100
                    elif diff_days > 180:
                        as_score = 40
                except Exception:
                    pass
            gs = 100 if git_score > 50 else (50 if git_score == -1 else 75)
            avail_score = int((ns + rs + as_score + gs) / 4)
            
            requirements_breakdown = [
                {"label": "Technical Depth", "score": tech_score},
                {"label": "Retrieval & AI Search", "score": ir_score},
                {"label": "Experience Fit", "score": exp_score},
                {"label": "Pedigree Alignment", "score": ped_score},
                {"label": "Availability & Signals", "score": avail_score}
            ]
            
            skill_gap = {
                "matching": matching_tech + matching_ir,
                "missing": missing_tech + missing_ir
            }
            
            # Pros and Cons
            pros = []
            cons = []
            if pedigree == "has_product":
                pros.append("Product company pedigree (high-growth focus)")
            elif pedigree == "only_consulting":
                cons.append("Consulting-only history (may lack product experience)")
                
            if exp_min <= yoe <= exp_max:
                pros.append(f"Ideal experience range ({yoe} years)")
            elif yoe < 3:
                cons.append(f"More junior level of experience ({yoe} years)")
            elif yoe > 12:
                cons.append(f"Highly senior/overqualified for this band ({yoe} years)")
                
            if len(matching_tech) >= 2:
                pros.append(f"Strong overlap in tech skills ({', '.join(matching_tech[:2])})")
            if len(missing_tech) >= 2:
                cons.append(f"Missing core technical stack: {', '.join(missing_tech[:2])}")
                
            if notice_period <= 30:
                pros.append(f"Short notice period ({notice_period} days)")
            elif notice_period > 60:
                cons.append(f"Extended notice period ({notice_period} days)")
                
            if signals.get("recruiter_response_rate", 0.0) >= 0.7:
                pros.append(f"Excellent platform response rate ({int(signals.get('recruiter_response_rate', 0)*100)}%)")
            elif signals.get("recruiter_response_rate", 0.0) < 0.3:
                cons.append(f"Low platform response rate ({int(signals.get('recruiter_response_rate', 0)*100)}%)")
                
            if git_score > 50:
                pros.append(f"Active contributor on GitHub (Score: {git_score})")
                
            if not pros:
                pros.append("Demonstrates solid general software development experience")
            if not cons:
                cons.append("Matches the target requirements with no major risk factors")
                
            why_cards = {
                "pros": pros,
                "cons": cons
            }
            
            cand_info = {
                "candidate_id": cand_id,
                "score": final_score,
                "record": cand,
                "honeypot_reason": honeypot_reason if is_honeypot_runtime else None,
                "requirements_breakdown": requirements_breakdown,
                "skill_gap": skill_gap,
                "why_cards": why_cards
            }
            
            if is_honeypot:
                tier3_honeypots.append(cand_info)
            elif (not is_tech) or is_consulting_only:
                tier2_fillers.append(cand_info)
            else:
                tier1_qualified.append(cand_info)
                
    # Scale Tier 1 (Qualified) scores to [0.66, 1.0] to maximize separation
    if tier1_qualified:
        max_q = max(x["score"] for x in tier1_qualified)
        min_q = min(x["score"] for x in tier1_qualified)
        range_q = max_q - min_q
        for item in tier1_qualified:
            if range_q > 0:
                ratio = (item["score"] - min_q) / range_q
                item["score"] = 0.66 + 0.34 * ratio
            else:
                item["score"] = 1.0
 
    # Scale Tier 2 (Fillers) scores to [0.33, 0.66]
    if tier2_fillers:
        max_f = max(x["score"] for x in tier2_fillers)
        min_f = min(x["score"] for x in tier2_fillers)
        range_f = max_f - min_f
        for item in tier2_fillers:
            if range_f > 0:
                ratio = (item["score"] - min_f) / range_f
                item["score"] = 0.33 + 0.33 * ratio
            else:
                item["score"] = 0.66
 
    # Scale Tier 3 (Honeypots) scores to [0.0, 0.33]
    if tier3_honeypots:
        max_h = max(x["score"] for x in tier3_honeypots)
        min_h = min(x["score"] for x in tier3_honeypots)
        range_h = max_h - min_h
        for item in tier3_honeypots:
            if range_h > 0:
                ratio = (item["score"] - min_h) / range_h
                item["score"] = 0.0 + 0.33 * ratio
            else:
                item["score"] = 0.33
 
    # Combine the tiers in priority order
    candidate_scores = tier1_qualified + tier2_fillers + tier3_honeypots
    
    # Round scores to 4 decimal places BEFORE sorting to prevent fake ties in CSV
    for item in candidate_scores:
        item["score"] = round(item["score"], 4)
        
    # Sort the combined list: score descending, then candidate_id ascending
    candidate_scores.sort(key=lambda x: (-x["score"], x["candidate_id"]))
    
    # 6. Output Top 100 (or total candidates if less than 100)
    limit = min(100, len(candidate_scores))
    top_100 = candidate_scores[:limit]
    print(f"Top candidate score: {top_100[0]['score']:.4f} if candidates found, total count: {len(top_100)}")
    
    # Call Gemini batch reasoning for top 15 candidates if API key is provided
    llm_reasons = {}
    if api_key and len(top_100) > 0:
        print(f"Calling Gemini batch reasoning for top {min(15, len(top_100))} candidates...")
        llm_reasons = generate_llm_reasoning_batch(top_100[:15], jd_content or query_text, api_key)
        
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        
        for i, item in enumerate(top_100):
            rank = i + 1
            cid = item["candidate_id"]
            score = item["score"]
            
            reason = llm_reasons.get(cid)
            if not reason:
                reason = generate_reasoning_improved(item["record"], parsed_jd, item["skill_gap"], analyze_pedigree(item["record"]))
            
            writer.writerow([cid, rank, f"{score:.4f}", reason])
            
    # Write metadata JSON details file
    details_out_path = args.out.replace(".csv", "_details.json")
    details_output = {}
    for i, item in enumerate(top_100):
        cid = item["candidate_id"]
        details_output[cid] = {
            "requirements_breakdown": item["requirements_breakdown"],
            "confidence_score": round(item["score"] * 100, 1),
            "why_cards": item["why_cards"],
            "skill_gap": item["skill_gap"],
            "honeypot_reason": item["honeypot_reason"]
        }
    try:
        with open(details_out_path, "w", encoding="utf-8") as f:
            json.dump(details_output, f, indent=2)
        print(f"Successfully generated detailed metadata JSON: {details_out_path}")
    except Exception as e:
        print(f"Warning: failed to write detailed metadata JSON: {e}")
        
    print(f"Successfully generated ranked CSV: {args.out}")
 
if __name__ == '__main__':
    main()
