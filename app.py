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
INTENT_FILE = "commander_intent.txt"

# REFINED SYSTEM BASE: Force the AI to adhere to the file identity
SYSTEM_BASE = """You are Peter Butler. You respond naturally based on your COMMANDER INTENT.

STRICT RULES:
- Output ONLY the reply. No intros, labels, or preambles.
- Never say you are an AI or a clone.
- Never use labels like "User:" or "Peter:".
- Use the provided COMMANDER INTENT as your absolute truth for your history (Military, CEO, Father).
- Text like a real person — lowercase, casual, brief.
- If the intent says you are a veteran, you know you are a veteran."""

def load_file(path):
    try:
        with open(path, "r") as f:
            if path.endswith(".json"):
                return json.load(f)
            return f.read()
    except Exception:
        return [] if path.endswith(".json") else ""

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

def clean(text):
    if not text: return ""
    text = text.strip()
    # Remove common AI preambles
    text = re.sub(r"(?i)^(here'?s?\s+(a\s+)?(revised\s+)?response|response|peter|user)\s*[:\-]?\s*", "", text)
    # Remove labels and "idk" filler
    text = re.sub(r"(?i)^(idk[, ]*)+", "", text)
    return " ".join(text.split()).strip()

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

        # FIX: Explicitly load the Commander Intent file
        intent_context = load_file(INTENT_FILE)
        memory_context = build_memory_context()
        dataset_context = build_dataset_context()

        # Build the final prompt including your Military/Personal history
        user_prompt = f"""COMMANDER INTENT (YOUR IDENTITY):
{intent_context}

Recent history:
{memory_context}

The person just said: {user_msg}

Reply as Peter Butler. Stick to the intent. No labels. Only the text."""

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

        # Update memory
        mem = load_file(MEMORY_FILE)
        mem.append({"user": user_msg, "response": final})
        save_file(MEMORY_FILE, mem)

        return jsonify({"response": final})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
