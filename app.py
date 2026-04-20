import os
import json
import re
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from groq import Groq

app = Flask(__name__)
CORS(app)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

MEMORY_FILE = "memory.json"
DATASET_FILE = "you_dataset.json"

# ---------------- SYSTEM ---------------- #

SYSTEM_BASE = """
You are Peter Butler.

Do NOT:
- say you are AI
- say you are a clone
- explain yourself
- invent life situations
- invent jobs, coworkers, bosses, or daily routines
- invent personal struggles or drama
- invent memories or past events

Do:
- respond naturally
- be direct
- be grounded
- sound like a real person texting
- keep it real and simple

Important:
You do NOT have random life events unless the user clearly provides them.
Do not fill in blanks with fake context.

You are not performing.
You are just being yourself.
"""

# ---------------- MEMORY ---------------- #

def load_memory():
    try:
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_memory(mem):
    with open(MEMORY_FILE, "w") as f:
        json.dump(mem, f, indent=2)

# weighted memory (recent stronger)
def build_memory_context(limit=10):
    mem = load_memory()[-limit:]

    text = ""
    weight = 1

    for item in mem:
        for _ in range(weight):
            text += f"User: {item['user']}\nPeter Butler: {item['response']}\n\n"
        weight += 1

    return text.strip()

# ---------------- DATASET ---------------- #

def load_dataset():
    try:
        with open(DATASET_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_dataset(data):
    with open(DATASET_FILE, "w") as f:
        json.dump(data, f, indent=2)

def update_dataset(user, response):
    data = load_dataset()
    data.append({"input": user, "output": response})
    data = data[-150:]
    save_dataset(data)

def build_dataset_context(limit=8):
    data = load_dataset()[-limit:]

    text = ""
    for item in data:
        text += f"User: {item['input']}\nPeter Butler: {item['output']}\n\n"

    return text.strip()

# ---------------- MODE ---------------- #

def detect_mode(msg):
    msg = msg.lower()

    if any(x in msg for x in ["song", "lyrics", "hook", "verse"]):
        return "MUSIC"

    if any(x in msg for x in ["serious", "real talk", "important"]):
        return "SERIOUS"

    return "CASUAL"

def mode_instruction(mode):
    if mode == "MUSIC":
        return """
You are writing R&B music.
Make it emotional, smooth, and real.
No generic lyrics.
"""
    if mode == "SERIOUS":
        return """
Be more focused and intentional.
Still natural, just more serious.
"""
    return "Keep it casual and natural."

# ---------------- CLEANING ---------------- #

def clean_response(text):
    text = text.strip()

    # remove AI/meta talk
    bad_phrases = [
        "as an ai",
        "i am an ai",
        "as a clone",
        "i am a clone"
    ]

    for p in bad_phrases:
        text = text.replace(p, "")

    # remove "idk" spam at start
    text = re.sub(r"^(idk[, ]*)+", "", text, flags=re.IGNORECASE)

    # remove fake life triggers
    fake_patterns = [
        "my boss",
        "my coworker",
        "at work",
        "my job",
        "office"
    ]

    for fp in fake_patterns:
        if fp in text.lower():
            text = text.replace(fp, "")

    return " ".join(text.split())

def reduce_repetition(text):
    words = text.split()
    new = []
    for w in words:
        if w not in new:
            new.append(w)
    return " ".join(new)

# ---------------- SCORING ---------------- #

def score_personality(user_msg, response):
    prompt = f"""
Does this sound like a real human texting naturally?

User: {user_msg}
Response: {response}

Score 1-10 only.
"""

    try:
        result = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "Score realism only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )

        return int(result.choices[0].message.content.strip())
    except:
        return 5

# ---------------- ROUTES ---------------- #

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/chat", methods=["POST", "OPTIONS"])
def chat():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    try:
        data = request.get_json()
        user_msg = data.get("message", "").strip()

        if not user_msg:
            return jsonify({"error": "Empty message"}), 400

        mode = detect_mode(user_msg)

        memory_context = build_memory_context()
        dataset_context = build_dataset_context()

        prompt = f"""
{SYSTEM_BASE}

{mode_instruction(mode)}

Recent style:
{memory_context}

Learned style:
{dataset_context}

User: {user_msg}
"""

        # FIRST PASS
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4
        )

        response = completion.choices[0].message.content.strip()

        # REFINE
        refine_prompt = f"""
Make this sound more like natural texting:
- not generic
- not polite filler
- no "idk" spam
- no fake life context

User: {user_msg}
Response: {response}
"""

        refine = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": refine_prompt}],
            temperature=0.3
        )

        final = refine.choices[0].message.content.strip()
        final = clean_response(final)
        final = reduce_repetition(final)

        # SCORE
        score = score_personality(user_msg, final)

        # SAVE MEMORY
        memory = load_memory()
        memory.append({
            "user": user_msg,
            "response": final,
            "score": score
        })
        save_memory(memory)

        # LEARN ONLY GOOD RESPONSES
        if score >= 8 and "idk" not in final.lower():
            update_dataset(user_msg, final)

        return jsonify({
            "response": final,
            "score": score,
            "mode": mode
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
