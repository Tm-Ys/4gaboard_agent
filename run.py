import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.web_ui.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_excludes=[".venv", "chroma_db", "docs_cache", "tmp"],
    )
