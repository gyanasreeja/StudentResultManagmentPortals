"""AI study recommendations: rule-based weak-topic detection + RAG (local embeddings + Groq LLM).

Improvements over v1:
- Models load lazily (server starts fast, no crash if GROQ_API_KEY is missing)
- Exact subject/topic match first, semantic search only as fallback
- Results cached per student until their marks change
- Falls back to the knowledge-base tip if the LLM call fails
"""
import hashlib
import json
import logging
import math
import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("ai")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

TOPIC_RESOURCES = [
    {"subject": "Math", "topic": "Trigonometry",
     "content": "Trigonometry covers sine, cosine, tangent, the unit circle, and angle identities. "
                "Practice unit circle problems and right-triangle ratios daily."},
    {"subject": "Math", "topic": "Algebra",
     "content": "Algebra covers solving linear and quadratic equations, factoring, and graphing. "
                "Practice factoring polynomials and solving multi-step equations."},
    {"subject": "Math", "topic": "Geometry",
     "content": "Geometry covers angles, triangles, circles, area, and volume. "
                "Practice proofs and draw accurate diagrams to visualize each problem."},
    {"subject": "Science", "topic": "Chemical bonding",
     "content": "Chemical bonding covers ionic, covalent, and metallic bonds, electronegativity and molecular "
                "shapes. Review electron configuration and Lewis structures."},
    {"subject": "Science", "topic": "Mechanics",
     "content": "Mechanics covers Newton's laws, force, motion, and energy. Practice free-body diagrams and F=ma problems."},
    {"subject": "Science", "topic": "Photosynthesis",
     "content": "Photosynthesis covers how plants turn sunlight, water and carbon dioxide into glucose and oxygen. "
                "Review the light and dark reactions and the role of chlorophyll."},
    {"subject": "Science", "topic": "Human anatomy",
     "content": "Human anatomy covers the circulatory, respiratory, digestive and nervous systems. "
                "Practice labeling diagrams and tracing the path of blood or food."},
    {"subject": "English", "topic": "Grammar",
     "content": "Grammar covers sentence structure, tenses, parts of speech and punctuation. "
                "Practice subject-verb agreement and rewriting sentences in different tenses."},
    {"subject": "English", "topic": "Comprehension",
     "content": "Comprehension covers a passage's main idea, tone and inference. "
                "Summarize paragraphs in your own words and answer inference-based questions."},
    {"subject": "English", "topic": "Essay writing",
     "content": "Essay writing covers introduction, body paragraphs and conclusion around a clear thesis. "
                "Outline your argument before writing and use linking words."},
    {"subject": "Hindi", "topic": "Vyakaran",
     "content": "Vyakaran (grammar) covers sangya, sarvanam, kriya and vakya sanrachna. "
                "Identify parts of speech and correct sentence structure in short passages."},
    {"subject": "Hindi", "topic": "Nibandh Lekhan",
     "content": "Nibandh lekhan covers bhoomika, vishay-vastu and upsanhaar. "
                "Write structured paragraphs on a single clear topic."},
    {"subject": "Hindi", "topic": "Kavya",
     "content": "Kavya covers alankar, ras and the central theme of a poem. "
                "Identify the poet's message and explain difficult lines in simple words."},
]

SEMANTIC_MIN_SCORE = 0.35
_cache: dict = {}


# ------------------------------------------------------------ lazy resources
@lru_cache(maxsize=1)
def _embeddings():
    from langchain_huggingface import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")


@lru_cache(maxsize=1)
def _kb_vectors():
    return _embeddings().embed_documents([r["content"] for r in TOPIC_RESOURCES])


@lru_cache(maxsize=1)
def _llm():
    from langchain_groq import ChatGroq
    return ChatGroq(model=GROQ_MODEL, api_key=GROQ_API_KEY, temperature=0.4, timeout=30, max_retries=1)


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _retrieve(subject: str, topic: str):
    """Exact match first; semantic search (RAG retrieval) as fallback."""
    for r in TOPIC_RESOURCES:
        if r["subject"].lower() == subject.lower() and r["topic"].lower() == topic.lower():
            return r
    try:
        q = _embeddings().embed_query(f"{subject} {topic}")
        score, best = max(((_cosine(q, v), r) for v, r in zip(_kb_vectors(), TOPIC_RESOURCES)), key=lambda p: p[0])
        return best if score >= SEMANTIC_MIN_SCORE else None
    except Exception:
        log.exception("Embedding retrieval failed")
        return None


# ------------------------------------------------------------ public API
def detect_weak_topics(topic_results, threshold=0.6):
    """Rule-based (no LLM). topic_results: dicts with subject, topic, marks, max_marks."""
    weak = []
    for r in topic_results:
        pct = r["marks"] / r["max_marks"] if r["max_marks"] else 0
        if pct < threshold:
            weak.append({"subject": r["subject"], "topic": r["topic"], "score_pct": round(pct * 100, 1)})
    return sorted(weak, key=lambda w: w["score_pct"])


def _fallback(weak_topics, chunks):
    tips = " ".join(chunks) if chunks else "Revisit your class notes and practice past questions."
    names = ", ".join(f"{w['topic']} ({w['subject']})" for w in weak_topics)
    return f"Focus on {names}. {tips}"


def generate_recommendation(student_roll, weak_topics):
    if not weak_topics:
        return "Great work! No weak areas detected. Keep up the consistent performance across all topics."

    key = hashlib.sha256(json.dumps([student_roll, weak_topics], sort_keys=True).encode()).hexdigest()
    if key in _cache:
        return _cache[key]

    chunks = []
    for w in weak_topics:
        match = _retrieve(w["subject"], w["topic"])
        if match:
            chunks.append(f"{w['subject']} - {w['topic']}: {match['content']}")

    if not GROQ_API_KEY:
        return _fallback(weak_topics, chunks)

    weak_summary = ", ".join(f"{w['subject']} ({w['topic']}, {w['score_pct']}%)" for w in weak_topics)
    prompt = f"""You are a supportive academic advisor giving a student direct, spoken feedback.

Student's weak areas: {weak_summary}

Relevant topic background:
{chr(10).join(chunks) or 'None available - use general study advice.'}

Write a short (3-4 sentence) personalized recommendation, speaking directly to the student using "you".
Name the specific weak topics and give one concrete study tip per topic. Be encouraging.
Do not use a greeting, sign-off, letter format, placeholder text, or markdown. Just the feedback itself."""

    try:
        text = _llm().invoke(prompt).content.strip()
        _cache[key] = text
        return text
    except Exception:
        log.exception("Groq call failed - using fallback")
        return _fallback(weak_topics, chunks)