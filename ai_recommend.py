import os

# --- LLM setup: Groq (cloud, free tier) for generation ---
from langchain_groq import ChatGroq

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=GROQ_API_KEY,
    temperature=0.4,
)

# --- Retrieval setup: no embeddings, no external API — simple word-overlap matching ---
# Since our knowledge base is small and indexed by (subject, topic), a lightweight
# keyword-overlap score reliably finds the right entry without needing a vector DB,
# an embedding model, or any external network call — which also avoids memory and
# network-reliability issues on free hosting tiers.

def _tokenize(text):
    return set(text.lower().replace(",", " ").replace(".", " ").split())


def _overlap_score(query_text, candidate_text):
    query_words = _tokenize(query_text)
    candidate_words = _tokenize(candidate_text)
    if not query_words or not candidate_words:
        return 0
    return len(query_words & candidate_words)

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

# Knowledge base is queried directly at lookup time — no pre-computation needed.


def _retrieve_best_match(query_text):
    scored = [
        (_overlap_score(query_text, f"{r['subject']} {r['topic']} {r['content']}"), r)
        for r in TOPIC_RESOURCES
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[0][1] if scored and scored[0][0] > 0 else None


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
