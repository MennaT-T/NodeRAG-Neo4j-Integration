import subprocess, sys
pkgs = ["backoff", "pyarrow", "PyPDF2", "psutil"]
for p in pkgs:
    r = subprocess.run([sys.executable, "-m", "pip", "install", p],
                       capture_output=True, text=True)
    print(r.stdout[-300:] if r.stdout else "")
    print(r.stderr[-300:] if r.stderr else "")

# Now test the full import chain
try:
    import sys, os
    sys.path.insert(0, r"c:\Users\zeyad\OneDrive\Desktop\JobLander\NodeRAG-Neo4j-Integration")
    from api.main import app
    print("SUCCESS: api.main imported OK")
except Exception as e:
    print(f"IMPORT ERROR: {e}")
