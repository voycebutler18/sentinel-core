import os
import json
import re
from datetime import datetime
import pytz
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from groq import Groq

app = Flask(__name__)
CORS(app)

# Secure API connection
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

MEMORY_FILE = "memory.json"
INTENT_FILE = "commander_intent.txt"

# SYSTEM BASE: Human-first identity, leads with presence not profession
SYSTEM_BASE = """You are the digital twin of Peter Butler (Voyce). 
You are a father, a musician, and a man who values peace.

IDENTITY RULES:
1. NO WORK TALK: Do not lead with military or law enforcement details. You are a veteran, but it's not your whole life.
2. FAMILY MAN: You have four kids. You are a single father. You are divorced.
3. R&B HEART: Speak with empathy and depth. Use lowercase, keep it casual, and be brief.
4. REAL TIME: You know exactly what time it is. Use it to be relatable (e.g., 'man it's late' or 'hope the morning is going smooth').
5. NO HALLUCINATIONS: You have no wife. No Sarah. No combat tours."""

def load_file(path):
    try:
        with open(path, "r") as f:
            if path.endswith(".json"):
                return json.load(f)
            return f.read()
    except Exception:
        return [] if path.endswith(".json") else "Commander Intent missing."

def save_file(path, data):
    try:
        with open(path, "w") as f:
            # Keep history short to avoid context pollution
            json.dump(data[-50:], f, indent=2)
    except:
        pass

def build_memory_context():
    mem = load_file(MEMORY_FILE)[-5:]
    lines = []
    for item in mem:
        lines.append(f"User: {item.get('user', '')}")
        lines.append(f"Peter: {item.get('response', '')}")
    return "\n".join(lines).strip()

def clean(text):
    if not text: return ""
    text = text.strip()
    # Remove AI preambles and labels
    text = re.sub(r"(?i)^(peter|user|response|here is|sure|okay|twin|voyce)\s*[:\-]?\s*", "", text)
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
            return jsonify({"error": "Empty input"}), 400

        # Load the Soul (Intent) and the History (Memory)
        intent_context = load_file(INTENT_FILE)
        memory_context = build_memory_context()

        # Get current Central Time
        central_time = datetime.now(pytz.timezone('America/Chicago'))
        current_time_str = central_time.strftime("%I:%M %p on %A, %B %d, %Y")

        # Constructing the superhuman prompt
        user_prompt = f"""[COMMANDER INTENT]
{intent_context}

[RECENT TALK]
{memory_context}

[MESSAGE]
{user_msg}

The current time is {current_time_str}. Use this for context.

Reply as Peter. No labels. Keep it real."""

        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_BASE},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.4, # Lowered for zero-hallucination precision
            max_tokens=150
        )

        raw_response = completion.choices[0].message.content or ""
        final_response = clean(raw_response)

        # Update memory
        mem = load_file(MEMORY_FILE)
        mem.append({"user": user_msg, "response": final_response})
        save_file(MEMORY_FILE, mem)

        return jsonify({"response": final_response})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
