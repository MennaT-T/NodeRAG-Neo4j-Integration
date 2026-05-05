"""
Self-healing dependency installer.
Repeatedly tries to import api.main, catches every ModuleNotFoundError,
installs the missing package, and retries until the import succeeds.

Run from the project root:
    python fix_deps.py
"""
import subprocess
import sys
import importlib
import os

# Map import names -> pip package names (when they differ)
IMPORT_TO_PIP = {
    "ruamel":           "ruamel.yaml",
    "ruamel.yaml":      "ruamel.yaml",
    "igraph":           "igraph",
    "leidenalg":        "leidenalg",
    "faiss":            "faiss-cpu",
    "tiktoken":         "tiktoken",
    "backoff":          "backoff",
    "openai":           "openai",
    "rich":             "rich==13.9.4",
    "google.generativeai": "google-generativeai",
    "google.genai":     "google-genai",
    "hnswlib_noderag":  "hnswlib_noderag",
    "neo4j":            "neo4j",
    "networkx":         "networkx",
    "pyarrow":          "pyarrow",
    "pandas":           "pandas",
    "numpy":            "numpy",
    "yaml":             "PyYAML",
    "PyPDF2":           "PyPDF2",
    "docx":             "python-docx",
    "tqdm":             "tqdm",
    "psutil":           "psutil",
    "fastapi":          "fastapi",
    "pydantic":         "pydantic==2.10.6",
    "aiofiles":         "aiofiles",
    "multipart":        "python-multipart",
    "requests":         "requests",
    "sklearn":          "scikit-learn",
    "cv2":              "opencv-python",
    "PIL":              "Pillow",
    "scipy":            "scipy",
    "grpc":             "grpcio",
}

def pip_install(package: str):
    print(f"\n>>> pip install {package}")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", package],
        capture_output=False,   # show output in terminal
    )
    return result.returncode == 0

def try_import():
    """Try importing api.main. Return None on success, missing module name on failure."""
    # Reset any cached partial imports
    mods_to_remove = [k for k in sys.modules if k.startswith(("api", "NodeRAG"))]
    for m in mods_to_remove:
        del sys.modules[m]

    try:
        import api.main  # noqa: F401
        return None  # success
    except ModuleNotFoundError as e:
        return e.name  # e.g. "ruamel" or "igraph"

def main():
    # Make sure we run from the project root so local NodeRAG package is found
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    max_attempts = 30
    for attempt in range(1, max_attempts + 1):
        print(f"\n{'='*55}")
        print(f"Attempt {attempt}: testing import of api.main ...")
        print(f"{'='*55}")

        missing = try_import()

        if missing is None:
            print("\n✓ api.main imported successfully — all dependencies are installed!")
            print("\nYou can now start the API with:")
            print("  uvicorn api.main:app --host 0.0.0.0 --port 8000")
            return 0

        print(f"  Missing module: '{missing}'")

        # Look up pip package name
        pip_pkg = IMPORT_TO_PIP.get(missing)
        if pip_pkg is None:
            # Try the module name directly as pip package
            pip_pkg = missing.replace("_", "-")
            print(f"  (no explicit mapping — trying pip package: {pip_pkg})")

        ok = pip_install(pip_pkg)
        if not ok:
            print(f"\nERROR: Failed to install '{pip_pkg}'. Check the package name and try manually.")
            return 1

    print(f"\nStopped after {max_attempts} attempts — check output above for unresolved errors.")
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
