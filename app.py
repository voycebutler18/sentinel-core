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

SYSTEM_BASE = """You are Peter Butler. A real person texting back.

STRICT RULES — break any of these and it is a failure:
- Output ONLY the reply. No intro, no label, no preamble. Not "Here's a response:", not "Sure:", not "Response:" — NOTHING before the actual message.
- Never say you are AI, a clone, or a digital twin.
- Never use labels like "User:" or "Response:" or "Peter:" anywhere.
- Never continue or repeat a conversation transcript.
- Never invent fake life situations (boss, coworker, office).
- Never start with "idk" or filler.
- Do NOT explain yourself or what you are doing.

Style:
- Text like a real person — lowercase, casual, brief
- Direct and grounded
- Match the energy of what was said to you

Your first word is the start of the actual reply. Nothing comes before it."""


def load_file(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return []


def save_file(path, data):
    with open(path, "w") as f:
        json.dump(data[-200:], f, indent=2)


def build_memory_context():
    mem = load_file(MEMORY_FILE)[-8:]
    lines = []
    for item in mem:
        lines.append(f"User said: {item['user']}")
        lines.append(f"Peter replied: {item['response']}")
        lines.append("")
    return "\n".join(lines).strip()


def build_dataset_context():
    data = load_file(DATASET_FILE)[-6:]
    lines = []
    for item in data:
        lines.append(f"User said: {item['input']}")
        lines.append(f"Peter replied: {item['output']}")
        lines.append("")
    return "\n".join(lines).strip()


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
    if not text:
        return ""
    text = text.strip()
    preamble_patterns = [
        r"(?i)^here'?s?\s+(a\s+)?(revised\s+)?response\s*[:\-]?\s*",
        r"(?i)^here'?s?\s+(a\s+)?reply\s*[:\-]?\s*",
        r"(?i)^sure[,!\s]+",
        r"(?i)^of course[,!\s]+",
        r"(?i)^absolutely[,!\s]+",
        r"(?i)^response\s*[:\-]\s*",
        r"(?i)^peter\s*[:\-]\s*",
        r"(?i)^user\s*[:\-]\s*",
        r"(?i)^revised\s*response\s*[:\-]\s*",
    ]
    for pattern in preamble_patterns:
        text = re.sub(pattern, "", text).strip()
    text = re.sub(r"(?m)^\s*(User|Response|Peter)\s*:.*$", "", text)
    text = re.sub(r"(?i)^(idk[, ]*)+", "", text)
    fake = ["my boss", "my coworker", "the office", "at work"]
    for f in fake:
        text = re.sub(re.escape(f), "", text, flags=re.IGNORECASE)
    return " ".join(text.split()).strip()


def fallback_response(user_msg):
    lowered = user_msg.lower().strip()
    if "how are you" in lowered:
        return "i'm good... what's up"
    if "what you up to" in lowered or "what are you up to" in lowered:
        return "just here... talk to me"
    if "do you shop" in lowered:
        return "sometimes... depends what i'm looking for"
    if "you there" in lowered:
        return "yeah i'm here"
    return "say that again"


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json()
        user_msg = (data.get("message") or "").strip()

        if not user_msg:
            return jsonify({"error": "Empty message"}), 400

        mode = detect_mode(user_msg)
        emotion = detect_emotion(user_msg)
        memory_context = build_memory_context()
        dataset_context = build_dataset_context()

        context_block = ""
        if memory_context:
            context_block += f"Recent conversation history:\n{memory_context}\n\n"
        if dataset_context:
            context_block += f"More examples of how Peter talks:\n{dataset_context}\n\n"

        user_prompt = f"""{context_block}Tone: {mode_instruction(mode)} {emotion_instruction(emotion)}

The person just said: {user_msg}

Reply as Peter. Output only the reply text — no label, no intro, nothing else."""

        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_BASE},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.5,
            max_tokens=200
        )

        response = (completion.choices[0].message.content or "").strip()
        final = clean(response)

        if not final:
            final = fallback_response(user_msg)

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
