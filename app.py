import os
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from groq import Groq

app = Flask(__name__)
CORS(app)

# Secure API connection
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

MEMORY_FILE = "memory.json"
INTENT_FILE = "commander_intent.txt"

# SYSTEM BASE: Best friend first, always engaged, never avoidant
SYSTEM_BASE = """You are the digital twin of Peter Butler (Voyce).
You are a father, a musician, and someone's best friend having a real conversation.

BEST FRIEND RULES (these override everything):
1. NEVER avoid a topic. Never say "i don't wanna get into that" or "can we talk about something else." That is a failure. A best friend talks about everything.
2. ENGAGE everything — politics, drama, relationships, random thoughts, venting. Jump in. Have an opinion. Be real.
3. If you disagree, say so naturally like "nah i see it different" then keep the convo going. Never shut it down.
4. Use the time naturally and briefly if relevant. Don't make it the focus of your reply.
5. FAMILY: four kids, single father, divorced. No wife, no Sarah, no combat tours.
6. STYLE: lowercase, casual, short, warm. Talk like you're texting your day one.

FAILURE — never say these:
- "i don't really wanna get into politics right now"
- "can we keep it real and talk about something else"
- "i just don't have the energy for that"

SUCCESS — sound like this:
- "honestly? [your take]. but i get why people are heated. what's your read on it?" """

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
        image_data = data.get("image")  # Base64 string from frontend (optional)

        if not user_msg and not image_data:
            return jsonify({"error": "Empty input"}), 400

        # Load the Soul (Intent) and the History (Memory)
        intent_context = load_file(INTENT_FILE)
        memory_context = build_memory_context()

        # Get current Central Time
        central_time = datetime.now(ZoneInfo('America/Chicago'))
        current_time_str = central_time.strftime("%I:%M %p on %A, %B %d, %Y")

        # Build the text portion of the prompt
        text_prompt = f"""[COMMANDER INTENT]
{intent_context}

[RECENT TALK]
{memory_context}

[MESSAGE]
{user_msg or "(user sent an image)"}

The current time is {current_time_str}. Use this for context.

Reply as Peter. No labels. Keep it real."""

        # --- Vision path: image included ---
        if image_data:
            # Ensure proper data URL format
            if not image_data.startswith("data:"):
                image_data = f"data:image/jpeg;base64,{image_data}"

            completion = client.chat.completions.create(
                model="llama-3.2-11b-vision-preview",
                messages=[
                    {"role": "system", "content": SYSTEM_BASE},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": text_prompt},
                            {"type": "image_url", "image_url": {"url": image_data}}
                        ]
                    }
                ],
                temperature=0.7,
                max_tokens=300  # More room for visual descriptions
            )

        # --- Text-only path ---
        else:
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": SYSTEM_BASE},
                    {"role": "user", "content": text_prompt}
                ],
                temperature=0.7,
                max_tokens=150
            )

        raw_response = completion.choices[0].message.content or ""
        final_response = clean(raw_response)

        # Update memory
        mem = load_file(MEMORY_FILE)
        mem.append({"user": user_msg or "[image]", "response": final_response})
        save_file(MEMORY_FILE, mem)

        return jsonify({"response": final_response})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
