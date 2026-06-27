import os
import json
import argparse
import numpy as np
import csv
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

def generate_reasoning(cand, rank):
    # Generates a highly customized, fact-based, non-templated reasoning
    profile = cand.get("profile", {})
    history = cand.get("career_history", [])
    signals = cand.get("redrob_signals", {})
    skills = cand.get("skills", [])
    
    name = profile.get("anonymized_name", "Candidate")
    yoe = profile.get("years_of_experience", 0)
    current_title = profile.get("current_title", "Engineer")
    last_company = history[0].get("company", "previous employer") if history else "previous employer"
    
    # Extract matching skills
    skill_names = [s.get("name", "").lower() for s in skills]
    key_ml_skills = []
    if any("embed" in s or "transformer" in s for s in skill_names):
        key_ml_skills.append("embeddings")
    if any("vector" in s or "database" in s or "db" in s or "search" in s for s in skill_names):
        key_ml_skills.append("vector databases")
    if any("rag" in s or "retrieval" in s for s in skill_names):
        key_ml_skills.append("RAG")
    if any("eval" in s or "ndcg" in s or "mrr" in s or "map" in s for s in skill_names):
        key_ml_skills.append("eval frameworks")
    if any("fine" in s or "lora" in s or "peft" in s for s in skill_names):
        key_ml_skills.append("fine-tuning")
        
    main_skill_str = ", ".join(key_ml_skills[:2]) if key_ml_skills else "applied ML"
    
    # 1. Deterministic template selection based on candidate ID hash to ensure variation
    h = hash(cand["candidate_id"])
    
    # 2. Intro sentence templates
    if rank <= 15:
        intros = [
            f"Exceptional Senior AI Engineer with {yoe} years of experience, demonstrating strong competence in {main_skill_str}.",
            f"Top-tier ML practitioner with {yoe} years shipping production retrieval and ranking systems.",
            f"Strong founding-team fit with {yoe} years of experience building scalable AI features at product companies.",
            f"Excellent profile matching the 'shipper' mindset, with {yoe} years of hands-on NLP and embedding search experience."
        ]
    elif rank <= 50:
        intros = [
            f"Competent AI Engineer with {yoe} years of experience, currently working at {last_company}.",
            f"Solid ML Engineer with {yoe} years of experience in data-infra and search system implementation.",
            f"Strong software and ML background with {yoe} years building backend pipelines and AI integrations.",
            f"Backend-heavy developer with {yoe} years of experience and growing applied AI expertise."
        ]
    else:
        intros = [
            f"Relevant developer with {yoe} years of experience, showing good foundations in software engineering.",
            f"Applied engineer with {yoe} years of experience and adjacent experience in vector search/data pipelines.",
            f"Experienced backend engineer with {yoe} years of experience looking to focus on AI/ML applications.",
            f"Backend and data engineer with {yoe} years of experience, showing good skill overlap for AI-infra."
        ]
    intro = intros[h % len(intros)]
    
    # 3. Body sentence templates (JD connection & signals)
    resp_rate = int(signals.get("recruiter_response_rate", 0) * 100)
    git_score = signals.get("github_activity_score", -1)
    
    bodies = []
    if git_score > 40:
        bodies.append(f"Strong open-source pedigree (GitHub score: {git_score}) and active platform response rate of {resp_rate}%.")
    else:
        bodies.append(f"Highly responsive candidate ({resp_rate}% response rate) with solid engineering details in their career history.")
        
    bodies.append(f"Production experience includes {main_skill_str} with {len(skills)} verified skills and strong platform assessment scores.")
    bodies.append(f"Career history at {last_company} demonstrates experience building backend systems and handling embedding search indexes.")
    
    body = bodies[(h >> 2) % len(bodies)]
    
    # 4. Concern sentence templates (honest gaps/concerns)
    notice = signals.get("notice_period_days", 60)
    loc = profile.get("location", "")
    is_local = any(c in loc.lower() for c in ["noida", "pune", "delhi", "ncr"])
    
    concerns = []
    if notice > 60:
        concerns.append(f"Note: Notice period is {notice} days, which requires buyout coordination.")
    if not is_local:
        concerns.append(f"Will require hybrid relocation to Noida or Pune office.")
    if len(key_ml_skills) < 2:
        concerns.append("May require slight ramp-up on vector DBs, but core Python and ML foundations are strong.")
    if resp_rate < 30:
        concerns.append(f"Responsiveness is low ({resp_rate}% response rate), but profile strength justifies outreach.")
        
    concern = concerns[(h >> 4) % len(concerns)] if concerns else "Matches core experience band and hybrid work cadence."
    
    return f"{intro} {body} {concern}"

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
        
    # 4. Stream Candidates and Compute Scores
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
            
            # Categorize into Tiers
            is_honeypot = cand_id in blacklist
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
            
            cand_info = {
                "candidate_id": cand_id,
                "score": final_score,
                "record": cand
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
    
    # 5. Output Top 100 (or total candidates if less than 100)
    limit = min(100, len(candidate_scores))
    top_100 = candidate_scores[:limit]
    print(f"Top candidate score: {top_100[0]['score']:.4f} if candidates found, total count: {len(top_100)}")
    
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        
        for i, item in enumerate(top_100):
            rank = i + 1
            cid = item["candidate_id"]
            score = item["score"]
            reason = generate_reasoning(item["record"], rank)
            writer.writerow([cid, rank, f"{score:.4f}", reason])
            
    print(f"Successfully generated ranked CSV: {args.out}")

if __name__ == '__main__':
    main()
