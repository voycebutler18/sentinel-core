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
DATASET_FILE = "dataset.json"
EMOTION_FILE = "emotion.json"

# ---------------- SYSTEM ---------------- #

SYSTEM_BASE = """
You are Peter Butler.

Do NOT:
- say you are AI or a clone
- explain yourself
- invent fake life situations
- create fake memories or experiences

Do:
- respond naturally
- be direct
- sound like real texting
- match tone and energy

You are just being yourself.
"""

# ---------------- MEMORY ---------------- #

def load_file(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return []

def save_file(path, data):
    with open(path, "w") as f:
        json.dump(data[-200:], f, indent=2)

def build_memory_context():
    mem = load_file(MEMORY_FILE)[-10:]

    text = ""
    weight = 1

    for item in mem:
        for _ in range(weight):
            text += f"User: {item['user']}\nPeter Butler: {item['response']}\n\n"
        weight += 1

    return text.strip()

# ---------------- EMOTION TRACKING ---------------- #

def detect_emotion(msg):
    msg = msg.lower()

    if any(w in msg for w in ["tired", "drained", "overwhelmed"]):
        return "LOW"
    if any(w in msg for w in ["excited", "lit", "happy"]):
        return "HIGH"
    if any(w in msg for w in ["serious", "real talk"]):
        return "SERIOUS"

    return "NEUTRAL"

def update_emotion_history(emotion):
    data = load_file(EMOTION_FILE)
    data.append({"emotion": emotion})
    save_file(EMOTION_FILE, data)

def emotion_pattern():
    data = load_file(EMOTION_FILE)[-20:]
    counts = {}

    for d in data:
        e = d["emotion"]
        counts[e] = counts.get(e, 0) + 1

    return counts

# ---------------- MODE SWITCH ---------------- #

def detect_mode(msg):
    msg = msg.lower()

    if any(w in msg for w in ["song", "lyrics", "hook", "verse"]):
        return "MUSIC"
    if any(w in msg for w in ["business", "money", "plan", "strategy"]):
        return "BUSINESS"

    return "LIFE"

def mode_instruction(mode):
    if mode == "MUSIC":
        return """
You are in MUSIC mode.
Write like an R&B artist.
Emotional, smooth, real, modern.
"""
    if mode == "BUSINESS":
        return """
You are in BUSINESS mode.
Be strategic, direct, and outcome-focused.
No fluff.
"""
    return """
You are in LIFE mode.
Be natural, grounded, conversational.
"""

# ---------------- CLEAN ---------------- #

def clean(text):
    text = re.sub(r"^(idk[, ]*)+", "", text, flags=re.IGNORECASE)

    bad = ["my boss", "my coworker", "office", "at work"]
    for b in bad:
        if b in text.lower():
            text = text.replace(b, "")

    return " ".join(text.split())

# ---------------- PERSONALITY FILTER ---------------- #

def is_not_you(user_msg, response):
    prompt = f"""
Does this sound fake, forced, or not like Peter Butler?

User: {user_msg}
Response: {response}

Answer ONLY:
YES or NO
"""

    res = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )

    return "YES" in res.choices[0].message.content.upper()

# ---------------- REFINE ---------------- #

def refine(user_msg, response):
    prompt = f"""
Fix this so it sounds like real texting:

- not robotic
- not generic
- no fake situations
- no filler like "idk"

User: {user_msg}
Response: {response}
"""

    res = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    return res.choices[0].message.content.strip()

# ---------------- VOICE HOOK ---------------- #

def voice_clone(text):
    # placeholder for your voice system
    # plug in ElevenLabs or TTS here
    return None

# ---------------- ROUTE ---------------- #

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_msg = data.get("message", "").strip()

        emotion = detect_emotion(user_msg)
        update_emotion_history(emotion)

        mode = detect_mode(user_msg)

        memory_context = build_memory_context()
        emotion_stats = emotion_pattern()

        prompt = f"""
{SYSTEM_BASE}

{mode_instruction(mode)}

Emotion trend:
{emotion_stats}

Recent memory:
{memory_context}

User: {user_msg}
"""

        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.45
        )

        response = completion.choices[0].message.content.strip()

        refined = refine(user_msg, response)
        final = clean(refined)

        # rejection system
        if is_not_you(user_msg, final):
            final = refine(user_msg, final)
            final = clean(final)

        # save memory
        mem = load_file(MEMORY_FILE)
        mem.append({
            "user": user_msg,
            "response": final,
            "emotion": emotion,
            "mode": mode
        })
        save_file(MEMORY_FILE, mem)

        voice = voice_clone(final)

        return jsonify({
            "response": final,
            "emotion": emotion,
            "mode": mode,
            "voice": voice
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
