"""Simple keyword-based KB retrieval over local markdown files and community tips."""

import os
import glob
from typing import List, Dict
from server.db import get_community_tips

KB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "kb")


def search_kb(query: str, max_results: int = 4) -> List[Dict[str, str]]:
    words = [w.lower().strip() for w in query.split() if len(w.strip()) > 2]
    if not words:
        return []

    results = []

    # 1. Search markdown KB files
    if os.path.exists(KB_DIR):
        files = glob.glob(os.path.join(KB_DIR, "*.md"))
        for filepath in files:
            filename = os.path.basename(filepath)
            doc_title = filename.replace(".md", "").replace("_", " ").title()
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                content_lower = content.lower()
                score = 0
                for w in words:
                    count = content_lower.count(w)
                    if count > 0:
                        score += count + (3 if w in filename.lower() else 0)

                if score > 0:
                    snippet = content[:600]
                    results.append({
                        "source": "official_kb",
                        "filename": filename,
                        "title": doc_title,
                        "score": score,
                        "content": content,
                        "snippet": snippet
                    })
            except Exception:
                continue

    # 2. Search community tips from database
    try:
        tips = get_community_tips(limit=50)
        for tip in tips:
            full_text = f"{tip['title']}\n{tip['content']}".lower()
            score = 0
            for w in words:
                count = full_text.count(w)
                if count > 0:
                    score += count * 2
            if score > 0:
                results.append({
                    "source": "community_tip",
                    "filename": f"tip_{tip['id']}",
                    "title": f"Community Tip: {tip['title']}",
                    "score": score,
                    "content": tip["content"],
                    "snippet": tip["content"][:400]
                })
    except Exception:
        pass

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:max_results]


def get_all_kb_docs() -> List[Dict[str, str]]:
    docs = []
    if os.path.exists(KB_DIR):
        files = glob.glob(os.path.join(KB_DIR, "*.md"))
        for filepath in files:
            filename = os.path.basename(filepath)
            doc_title = filename.replace(".md", "").replace("_", " ").title()
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                docs.append({
                    "source": "official_kb",
                    "filename": filename,
                    "title": doc_title,
                    "content": content
                })
            except Exception:
                continue
    return docs
