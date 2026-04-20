import os
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from groq import Groq

app = Flask(__name__)
CORS(app)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

MEMORY_FILE = "memory.json"
DATASET_FILE = "you_dataset.json"

SYSTEM_BASE = """
You are Peter Butler.

Do NOT:
- say you are AI
- say you are a clone
- invent stories or fake experiences

Do:
- respond naturally
- be direct
- be real
- sound like a real human texting

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

# weighted memory (recent > old)
def build_memory_context(limit=12):
    mem = load_memory()
    mem = mem[-limit:]

    text = ""
    weight = 1

    for item in mem:
        for _ in range(weight):
            text += f"User: {item['user']}\nPeter Butler: {item['response']}\n\n"
        weight += 1  # newer = stronger

    return text.strip()

# ---------------- DATASET BUILDER ---------------- #

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

    # keep dataset from getting huge
    data = data[-200:]

    save_dataset(data)

def build_dataset_context(limit=10):
    data = load_dataset()[-limit:]

    text = ""
    for item in data:
        text += f"User: {item['input']}\nPeter Butler: {item['output']}\n\n"

    return text.strip()

# ---------------- MOOD DETECTION ---------------- #

def detect_mode(msg):
    msg = msg.lower()

    if any(word in msg for word in ["song", "lyrics", "write", "verse", "hook"]):
        return "MUSIC"

    if any(word in msg for word in ["serious", "real talk", "be honest", "important"]):
        return "SERIOUS"

    return "CASUAL"

def get_mode_instruction(mode):
    if mode == "MUSIC":
        return """
You are in MUSIC MODE.
You are an R&B artist.
Write with emotion, melody, and real feeling.
Keep it modern, smooth, and relatable.
"""

    if mode == "SERIOUS":
        return """
Be more focused and direct.
Still natural, but more intentional.
No jokes unless appropriate.
"""

    return """
Keep it casual, natural, conversational.
"""

# ---------------- PERSONALITY SCORING ---------------- #

def score_personality(user_msg, response):
    check_prompt = f"""
Does this response sound like a real person texting naturally?

User: {user_msg}
Response: {response}

Score from 1-10 ONLY.
"""

    score = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "Score tone realism."},
            {"role": "user", "content": check_prompt}
        ],
        temperature=0.1
    )

    try:
        return int(score.choices[0].message.content.strip())
    except:
        return 5

# ---------------- CLEAN ---------------- #

def clean_response(text):
    text = text.strip()

    bad = ["as an ai", "as a clone", "i am an ai", "i am a clone"]

    for b in bad:
        text = text.replace(b, "")

    return " ".join(text.split())

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
        mode_instruction = get_mode_instruction(mode)

        memory_context = build_memory_context()
        dataset_context = build_dataset_context()

        full_prompt = f"""
{SYSTEM_BASE}

{mode_instruction}

Recent memory:
{memory_context}

Learned personality:
{dataset_context}

User: {user_msg}
"""

        # FIRST RESPONSE
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": full_prompt}],
            temperature=0.5
        )

        response_text = completion.choices[0].message.content.strip()

        # REFINE
        refine_prompt = f"""
Make this sound more like natural texting:
- not polite for no reason
- not generic
- real tone

User: {user_msg}
Response: {response_text}
"""

        refine = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": refine_prompt}],
            temperature=0.3
        )

        final = refine.choices[0].message.content.strip()
        final = clean_response(final)

        # SCORE IT
        score = score_personality(user_msg, final)

        # SAVE MEMORY
        memory = load_memory()
        memory.append({
            "user": user_msg,
            "response": final,
            "score": score
        })
        save_memory(memory)

        # AUTO DATASET UPDATE (only if good)
        if score >= 7:
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
