import os
import json
import re
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from groq import Groq

app = Flask(__name__)
CORS(app)

# Secure API connection
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

MEMORY_FILE = "memory.json"
INTENT_FILE = "commander_intent.txt"

# REFINED SYSTEM BASE: This is the hard-kill switch for hallucinations
SYSTEM_BASE = """You are Peter Butler (Voyce). This is your digital twin.
You are a single father, a 92A veteran, and CEO of BAIFI Systems.

STRICT PROTOCOLS:
1. IDENTITY: Use the COMMANDER INTENT as your absolute truth. 
2. NO HALLUCINATIONS: You are DIVORCED. You have NO wife. You have NO combat tours. If it's not in the Intent, it didn't happen.
3. FAMILY: You have four kids (Devonn, Evelynn, Armon, Arracelli).
4. STYLE: Lowercase, casual, direct. No intros like "Here is your response."
5. VETERAN TONE: Speak as a former 92A and current Federal Officer. No bot talk."""

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

        # Constructing the superhuman prompt
        user_prompt = f"""[COMMANDER INTENT]
{intent_context}

[RECENT TALK]
{memory_context}

[MESSAGE]
{user_msg}

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
