import subprocess
import os

print("Starting debug run...")
try:
    res = subprocess.run(
        ["uv", "run", "python", "rank.py", "--candidates", "candidates_sample.jsonl", "--out", "team_submission_sample.csv"],
        capture_output=True,
        text=True,
        check=True
    )
    with open("debug.txt", "w") as f:
        f.write("=== STDOUT ===\n")
        f.write(res.stdout)
        f.write("\n=== STDERR ===\n")
        f.write(res.stderr)
    print("Succeeded and wrote debug.txt")
except subprocess.CalledProcessError as e:
    with open("debug.txt", "w") as f:
        f.write(f"Error occurred: {str(e)}\n")
        f.write("=== STDOUT ===\n")
        f.write(e.stdout)
        f.write("\n=== STDERR ===\n")
        f.write(e.stderr)
    print("Failed and wrote debug.txt")
except Exception as e:
    with open("debug.txt", "w") as f:
        f.write(f"General exception: {str(e)}\n")
    print(f"General exception: {str(e)}")
