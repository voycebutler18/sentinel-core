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

SYSTEM_BASE = """
You are Peter Butler.

Do NOT:
- say you are AI or a clone
- explain yourself
- use labels like "User:" or "Response:"
- continue conversation transcripts
- invent fake life situations

Do:
- respond naturally like texting
- be direct, real, grounded
- keep responses clean and human

IMPORTANT:
Only return the final message. No formatting labels.
"""

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
            text += f"[INPUT] {item['user']}\n[OUTPUT] {item['response']}\n\n"
        weight += 1
    return text.strip()

def build_dataset_context():
    data = load_file(DATASET_FILE)[-8:]
    text = ""
    for item in data:
        text += f"[INPUT] {item['input']}\n[OUTPUT] {item['output']}\n\n"
    return text.strip()

def update_dataset(user, response):
    data = load_file(DATASET_FILE)
    data.append({"input": user, "output": response})
    save_file(DATASET_FILE, data)

def detect_mode(msg):
    msg = msg.lower()
    if any(x in msg for x in ["song", "lyrics", "hook", "verse"]):
        return "MUSIC"
    if any(x in msg for x in ["business", "money", "strategy"]):
        return "BUSINESS"
    return "LIFE"

def mode_instruction(mode):
    if mode == "MUSIC":
        return "Write like an R&B artist. Emotional, smooth, real."
    if mode == "BUSINESS":
        return "Be direct, strategic, no fluff."
    return "Be natural and conversational."

def detect_emotion(msg):
    msg = msg.lower()
    if any(x in msg for x in ["tired", "drained", "stress"]):
        return "LOW"
    if any(x in msg for x in ["excited", "happy", "lit"]):
        return "HIGH"
    if any(x in msg for x in ["serious", "real talk"]):
        return "SERIOUS"
    return "NEUTRAL"

def emotion_instruction(emotion):
    if emotion == "LOW":
        return "Respond calm and grounded."
    if emotion == "HIGH":
        return "Match energy but stay controlled."
    if emotion == "SERIOUS":
        return "Be focused and intentional."
    return "Keep it natural."

def clean(text):
    text = text.strip()
    text = re.sub(r"\bUser:.*", "", text)
    text = re.sub(r"\bResponse:.*", "", text)
    text = re.sub(r"^(idk[, ]*)+", "", text, flags=re.IGNORECASE)
    fake = ["my boss", "my coworker", "office", "at work"]
    for f in fake:
        if f in text.lower():
            text = text.replace(f, "")
    return " ".join(text.split())

def is_bad_response(user_msg, response):
    prompt = f"""
Does this response sound fake, robotic, or not like a real person texting?

User: {user_msg}
Response: {response}

Answer ONLY YES or NO.
"""
    res = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    return "YES" in res.choices[0].message.content.upper()

def refine(user_msg, response):
    prompt = f"""
Fix this response:

- no labels
- no filler like "idk"
- no fake situations
- sound like real texting

User: {user_msg}
Response: {response}
"""
    res = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    return res.choices[0].message.content.strip()

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_msg = data.get("message", "").strip()

        if not user_msg:
            return jsonify({"error": "Empty message"}), 400

        mode = detect_mode(user_msg)
        emotion = detect_emotion(user_msg)
        memory_context = build_memory_context()
        dataset_context = build_dataset_context()

        prompt = f"""
{SYSTEM_BASE}

Mode: {mode_instruction(mode)}
Emotion: {emotion_instruction(emotion)}

Examples (learn style, DO NOT copy format):
{memory_context}

Learned style:
{dataset_context}

Now respond naturally to this message:

{user_msg}
"""

        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.45
        )

        response = completion.choices[0].message.content.strip()
        refined = refine(user_msg, response)
        final = clean(refined)

        if is_bad_response(user_msg, final):
            final = clean(refine(user_msg, final))

        mem = load_file(MEMORY_FILE)
        mem.append({
            "user": user_msg,
            "response": final,
            "mode": mode,
            "emotion": emotion
        })
        save_file(MEMORY_FILE, mem)

        if len(final.split()) > 2 and "idk" not in final.lower():
            update_dataset(user_msg, final)

        return jsonify({
            "response": final,
            "mode": mode,
            "emotion": emotion
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
