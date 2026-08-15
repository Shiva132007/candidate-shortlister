import json
import os
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
os.environ["HF_HOME"] = os.path.join(WORKSPACE_DIR, ".hf_cache")
import argparse
import numpy as np
from sentence_transformers import SentenceTransformer

def compile_text_profile(cand):
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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=str, default=os.path.join(WORKSPACE_DIR, "[PUB] India_runs_data_and_ai_challenge", "[PUB] India_runs_data_and_ai_challenge", "India_runs_data_and_ai_challenge", "candidates.jsonl"))
    args = parser.parse_args()
    
    out_dir = WORKSPACE_DIR
    model_save_path = os.path.join(out_dir, "model", "all-MiniLM-L6-v2")
    
    # Load model locally
    print(f"Loading local SentenceTransformer model from {model_save_path}...")
    model = SentenceTransformer(model_save_path, local_files_only=True)
    
    # Read candidates and compile profiles
    print(f"Reading candidates from {args.candidates}...")
    candidate_ids = []
    texts = []
    
    with open(args.candidates, "r", encoding="utf-8-sig") as f:
        for line in f:
            if not line.strip():
                continue
            cand = json.loads(line)
            candidate_ids.append(cand["candidate_id"])
            texts.append(compile_text_profile(cand))
            
    print(f"Parsed {len(texts)} candidates.")
    
    # Start multi-process pool (uses all 8 cores by default)
    print("Starting multi-process pool for parallel encoding...")
    pool = model.start_multi_process_pool()
    
    # Generate embeddings
    print("Generating embeddings using multi-process encoding (this will be fast)...")
    embeddings = model.encode_multi_process(
        texts,
        pool,
        batch_size=512
    )
    
    # Stop the pool
    model.stop_multi_process_pool(pool)
    print("Multi-process pool stopped.")
    
    # Save embeddings and ID map
    emb_path = os.path.join(out_dir, "embeddings.npy")
    map_path = os.path.join(out_dir, "candidate_id_map.json")
    
    np.save(emb_path, embeddings.astype(np.float32))
    print(f"Saved embeddings to {emb_path} (Shape: {embeddings.shape})")
    
    id_map = {cid: idx for idx, cid in enumerate(candidate_ids)}
    with open(map_path, "w", encoding="utf-8") as out:
        json.dump(id_map, out)
    print(f"Saved candidate ID mapping to {map_path}")

if __name__ == '__main__':
    main()
