import os
import sys

# Forward execution to backend/rank.py
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from rank import main

if __name__ == "__main__":
    main()
