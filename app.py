import os
import json
import re
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from groq import Groq

app = Flask(__name__)
CORS(app)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

MEMORY_FILE = "memory.json"
DATASET_FILE = "you_dataset.json"

# ---------------- SYSTEM ---------------- #

SYSTEM_BASE = """
You are Peter Butler.

Do NOT:
- say you are AI or a clone
- explain yourself
- invent life situations, jobs, or fake experiences

Do:
- respond naturally
- be direct
- be grounded
- sound like real texting
- match tone and energy

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
        json.dump(mem[-200:], f, indent=2)

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
        json.dump(data[-200:], f, indent=2)

def update_dataset(user, response):
    data = load_dataset()
    data.append({"input": user, "output": response})
    save_dataset(data)

def build_dataset_context(limit=8):
    data = load_dataset()[-limit:]

    text = ""
    for item in data:
        text += f"User: {item['input']}\nPeter Butler: {item['output']}\n\n"

    return text.strip()

# ---------------- EMOTION DETECTION ---------------- #

def detect_emotion(msg):
    msg = msg.lower()

    if any(w in msg for w in ["tired", "drained", "stress", "overwhelmed"]):
        return "LOW"
    if any(w in msg for w in ["excited", "happy", "lit", "good mood"]):
        return "HIGH"
    if any(w in msg for w in ["serious", "real talk", "important"]):
        return "SERIOUS"

    return "NEUTRAL"

def emotion_instruction(emotion):
    if emotion == "LOW":
        return "Respond calmer, more grounded, supportive but not soft."
    if emotion == "HIGH":
        return "Match energy but keep control. Don’t be overhyped."
    if emotion == "SERIOUS":
        return "Be focused, intentional, direct."
    return "Keep tone natural."

# ---------------- TONE MATCH ---------------- #

def build_tone_reference():
    mem = load_memory()[-5:]
    tone = ""

    for m in mem:
        tone += m["user"] + "\n"

    return tone.strip()

# ---------------- CLEAN ---------------- #

def clean_response(text):
    text = text.strip()

    # remove idk spam
    text = re.sub(r"^(idk[, ]*)+", "", text, flags=re.IGNORECASE)

    # remove fake life patterns
    fake = ["my boss", "my coworker", "at work", "my job"]
    for f in fake:
        if f in text.lower():
            text = text.replace(f, "")

    return " ".join(text.split())

# ---------------- PERSONALITY FILTER ---------------- #

def personality_filter(user_msg, response):
    check = f"""
Does this sound like natural human texting?

User: {user_msg}
Response: {response}

Answer ONLY:
YES
or
NO
"""

    result = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": check}],
        temperature=0.1
    )

    return "YES" in result.choices[0].message.content.upper()

# ---------------- REFINE ---------------- #

def refine_response(user_msg, response):
    prompt = f"""
Fix this to sound more like natural texting:

- remove filler like "idk"
- no fake situations
- not overly polite
- real tone

User: {user_msg}
Response: {response}
"""

    res = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    return res.choices[0].message.content.strip()

# ---------------- ROUTES ---------------- #

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_msg = data.get("message", "").strip()

        emotion = detect_emotion(user_msg)
        memory_context = build_memory_context()
        dataset_context = build_dataset_context()
        tone_ref = build_tone_reference()

        prompt = f"""
{SYSTEM_BASE}

{emotion_instruction(emotion)}

User tone examples:
{tone_ref}

Recent style:
{memory_context}

Learned style:
{dataset_context}

User: {user_msg}
"""

        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.45
        )

        response = completion.choices[0].message.content.strip()

        # refine
        refined = refine_response(user_msg, response)
        final = clean_response(refined)

        # personality check
        is_valid = personality_filter(user_msg, final)

        if not is_valid:
            final = refine_response(user_msg, final)
            final = clean_response(final)

        # save memory
        memory = load_memory()
        memory.append({
            "user": user_msg,
            "response": final,
            "emotion": emotion
        })
        save_memory(memory)

        # learn only good responses
        if len(final.split()) > 2 and "idk" not in final.lower():
            update_dataset(user_msg, final)

        return jsonify({
            "response": final,
            "emotion": emotion
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
