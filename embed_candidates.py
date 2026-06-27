import json
import os
os.environ["HF_HOME"] = r"E:\AI-resume\.hf_cache"
import argparse
import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

def compile_text_profile(cand):
    profile = cand.get("profile", {})
    skills = cand.get("skills", [])
    history = cand.get("career_history", [])
    
    parts = []
    
    # 1. Headline & Title
    headline = profile.get("headline", "")
    current_title = profile.get("current_title", "")
    parts.append(f"Title: {current_title}")
    parts.append(f"Headline: {headline}")
    
    # 2. Summary
    summary = profile.get("summary", "")
    if summary:
        parts.append(f"Summary: {summary}")
        
    # 3. Skills
    if skills:
        skill_list = [s.get("name", "") for s in skills if s.get("name")]
        parts.append(f"Skills: {', '.join(skill_list)}")
        
    # 4. Career History
    if history:
        history_parts = []
        for job in history[:4]: # Last 4 jobs
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
    parser.add_argument("--candidates", type=str, default=r"E:\AI-resume\[PUB] India_runs_data_and_ai_challenge\[PUB] India_runs_data_and_ai_challenge\India_runs_data_and_ai_challenge\candidates.jsonl")
    parser.add_argument("--sample", type=int, default=None, help="Only embed first N candidates for testing")
    args = parser.parse_args()
    
    out_dir = r"E:\AI-resume"
    model_save_path = os.path.join(out_dir, "model", "all-MiniLM-L6-v2")
    
    # 1. Load and save SentenceTransformer model locally
    print("Loading and saving model locally...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    model.save(model_save_path)
    print(f"Model saved to {model_save_path}")
    
    # 2. Read candidates and compile profiles
    print(f"Reading candidates from {args.candidates}...")
    candidate_ids = []
    texts = []
    
    with open(args.candidates, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            cand = json.loads(line)
            candidate_ids.append(cand["candidate_id"])
            texts.append(compile_text_profile(cand))
            
            if args.sample and len(texts) >= args.sample:
                break
                
    print(f"Parsed {len(texts)} candidates.")
    
    # 3. Generate embeddings
    print("Generating embeddings (in batches)...")
    embeddings = model.encode(
        texts,
        batch_size=512,
        show_progress_bar=True,
        normalize_embeddings=True # Pre-normalize for fast cosine similarity via dot product
    )
    
    # 4. Save embeddings and ID map
    emb_filename = "embeddings_sample.npy" if args.sample else "embeddings.npy"
    map_filename = "candidate_id_map_sample.json" if args.sample else "candidate_id_map.json"
    
    emb_path = os.path.join(out_dir, emb_filename)
    map_path = os.path.join(out_dir, map_filename)
    
    # Save embeddings as float32 NumPy array
    np.save(emb_path, embeddings.astype(np.float32))
    print(f"Saved embeddings to {emb_path} (Shape: {embeddings.shape})")
    
    # Save ID mapping
    id_map = {cid: idx for idx, cid in enumerate(candidate_ids)}
    with open(map_path, "w", encoding="utf-8") as out:
        json.dump(id_map, out)
    print(f"Saved candidate ID mapping to {map_path}")

if __name__ == '__main__':
    main()
