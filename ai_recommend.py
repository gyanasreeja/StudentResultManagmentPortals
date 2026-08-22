import math
import os

# --- LLM setup: Groq (cloud, free tier) for generation ---
from langchain_groq import ChatGroq

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=GROQ_API_KEY,
    temperature=0.4,
)

# --- Embeddings setup: local HuggingFace model (no API key, no network call needed) ---
from langchain_huggingface import HuggingFaceEmbeddings

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# --- Topic knowledge base (expand this over time) ---
TOPIC_RESOURCES = [
    # Math
    {"subject": "Math", "topic": "Trigonometry",
     "content": "Trigonometry covers sine, cosine, tangent, the unit circle, and angle identities. "
                "Students should practice unit circle problems and right-triangle ratios daily."},
    {"subject": "Math", "topic": "Algebra",
     "content": "Algebra covers solving linear and quadratic equations, factoring, and graphing. "
                "Practice factoring polynomials and solving for x in multi-step equations."},
    {"subject": "Math", "topic": "Geometry",
     "content": "Geometry covers angles, triangles, circles, area, and volume calculations. "
                "Practice proofs and drawing accurate diagrams to visualize each problem."},

    # Science
    {"subject": "Science", "topic": "Chemical bonding",
     "content": "Chemical bonding covers ionic, covalent, and metallic bonds, electronegativity, "
                "and molecular shapes. Review electron configuration and Lewis structures."},
    {"subject": "Science", "topic": "Mechanics",
     "content": "Mechanics covers Newton's laws, force, motion, and energy. "
                "Practice free-body diagrams and F=ma problems."},
    {"subject": "Science", "topic": "Photosynthesis",
     "content": "Photosynthesis covers how plants convert sunlight, water, and carbon dioxide into "
                "glucose and oxygen. Review the light and dark reactions and the role of chlorophyll."},
    {"subject": "Science", "topic": "Human anatomy",
     "content": "Human anatomy covers the major organ systems: circulatory, respiratory, digestive, "
                "and nervous systems. Practice labeling diagrams and tracing the path of blood or food."},

    # English
    {"subject": "English", "topic": "Grammar",
     "content": "Grammar covers sentence structure, tenses, parts of speech, and punctuation rules. "
                "Practice identifying subject-verb agreement and rewriting sentences in different tenses."},
    {"subject": "English", "topic": "Comprehension",
     "content": "Reading comprehension covers understanding a passage's main idea, tone, and inference. "
                "Practice summarizing paragraphs in your own words and answering inference-based questions."},
    {"subject": "English", "topic": "Essay writing",
     "content": "Essay writing covers structuring an introduction, body paragraphs, and conclusion around "
                "a clear thesis. Practice outlining your argument before writing and using linking words."},

    # Hindi
    {"subject": "Hindi", "topic": "Vyakaran",
     "content": "Vyakaran (grammar) covers sangya, sarvanam, kriya, and vakya sanrachna. "
                "Practice identifying parts of speech and correcting sentence structure in short passages."},
    {"subject": "Hindi", "topic": "Nibandh Lekhan",
     "content": "Nibandh lekhan (essay writing) covers organizing an essay into bhoomika, vishay-vastu, "
                "and upsanhaar. Practice writing structured paragraphs on a single clear topic."},
    {"subject": "Hindi", "topic": "Kavya",
     "content": "Kavya (poetry) covers understanding alankar, ras, and the central theme of a poem. "
                "Practice identifying the poet's message and explaining difficult lines in simple words."},
]

# Pre-compute embeddings for the knowledge base once at startup.
# This is the "index" in a simple hand-rolled RAG pipeline (no vector DB needed
# for a small, fixed knowledge base like this one).
_kb_texts = [r["content"] for r in TOPIC_RESOURCES]
_kb_vectors = embeddings.embed_documents(_kb_texts)


def _cosine_similarity(vec_a, vec_b):
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _retrieve_best_match(query_text):
    query_vector = embeddings.embed_query(query_text)
    scored = [
        (_cosine_similarity(query_vector, kb_vec), resource)
        for kb_vec, resource in zip(_kb_vectors, TOPIC_RESOURCES)
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[0][1] if scored else None


def detect_weak_topics(topic_results, threshold=0.6):
    """Rule-based — no LLM. topic_results: list of dicts with subject, topic, marks, max_marks."""
    weak = []
    for r in topic_results:
        pct = r["marks"] / r["max_marks"] if r["max_marks"] else 0
        if pct < threshold:
            weak.append({"subject": r["subject"], "topic": r["topic"], "score_pct": round(pct * 100, 1)})
    return weak


def generate_recommendation(student_roll, weak_topics):
    if not weak_topics:
        return "Great work! No weak areas detected — keep up the consistent performance across all topics."

    context_chunks = []
    for w in weak_topics:
        match = _retrieve_best_match(f"{w['subject']} {w['topic']}")
        if match:
            context_chunks.append(f"{w['subject']} - {w['topic']}: {match['content']}")

    context = "\n".join(context_chunks)
    weak_summary = ", ".join(f"{w['subject']} ({w['topic']}, {w['score_pct']}%)" for w in weak_topics)

    prompt = f"""You are a supportive academic advisor giving a student direct, spoken feedback.

Student's weak areas: {weak_summary}

Relevant topic background:
{context}

Write a short (3-4 sentence) personalized recommendation, speaking directly to the student using "you".
Name the specific weak topics and give one concrete study tip per topic. Be encouraging.
Do not use a greeting, a sign-off, a letter format, or any placeholder text like [Student's Name] or [Your Name].
Do not use markdown formatting. Just the feedback itself, nothing else."""

    response = llm.invoke(prompt)
    return response.content
