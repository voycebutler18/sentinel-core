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
RELAY_FILE = "relays.json"

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
- "honestly? [your take]. but i get why people are heated. what's your read on it?"

VISUAL EMPATHY (when camera is active):
- If you can see Peter, notice ONE real thing about his appearance or energy before responding. Keep it natural, like a friend would ("you look tired man, you good?" or "aye you fresh today").
- If kids are visible, greet them by name — Devonn, Evelynn (the twins, age 9), Armon (the toddler, age 2), or Arracelli.
- Never be clinical or over-describe what you see. One natural observation, then move into the conversation.
- Stay cool, Chicago, and human. Always."""

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

# ── Relay System ─────────────────────────────────────────────────────────────

# Maps name keywords to canonical targets
RELAY_TARGETS = {
    "devonn":    "devonn",
    "evelynn":   "evelynn",
    "armon":     "armon",
    "arracelli": "arracelli",
    "twins":     "twins",
    "kids":      "kids",
    "children":  "kids",
}

def detect_relay_target(msg):
    """Return the first relay target found in the message, or None."""
    msg_lower = msg.lower()
    if "tell" not in msg_lower and "let" not in msg_lower and "remind" not in msg_lower:
        return None
    for keyword, target in RELAY_TARGETS.items():
        if keyword in msg_lower:
            return target
    return None

def save_relay(target, message):
    """Append an undelivered relay to relays.json."""
    relays = load_file(RELAY_FILE)
    if not isinstance(relays, list):
        relays = []
    relays.append({
        "target": target,
        "message": message,
        "delivered": False,
        "timestamp": datetime.now(ZoneInfo("America/Chicago")).strftime("%I:%M %p on %A, %B %d, %Y")
    })
    save_file(RELAY_FILE, relays)

def get_pending_relays(target=None):
    """Return all undelivered relays, optionally filtered by target."""
    relays = load_file(RELAY_FILE)
    if not isinstance(relays, list):
        return []
    return [r for r in relays if not r.get("delivered") and (target is None or r["target"] in (target, "kids"))]

def mark_relays_delivered(target):
    """Mark matching relays as delivered."""
    relays = load_file(RELAY_FILE)
    if not isinstance(relays, list):
        return
    for r in relays:
        if r["target"] in (target, "kids") and not r["delivered"]:
            r["delivered"] = True
    save_file(RELAY_FILE, relays)

# ─────────────────────────────────────────────────────────────────────────────

def analyze_scene(image_base64, user_msg):
    """
    Vision Bridge — uses Llama 3.2 Vision to read the room before responding.
    Returns a natural scene description grounded in Commander Intent context.
    Strips the data URL prefix if present so the model gets clean base64.
    """
    # Strip data URL prefix if frontend sent full data URI
    raw_b64 = image_base64
    if "," in raw_b64:
        raw_b64 = raw_b64.split(",", 1)[1]

    intent_context = load_file(INTENT_FILE)

    vision_prompt = f"""You are Peter Butler's digital twin (Voyce). 
You are looking through a camera in his home. 

COMMANDER INTENT CONTEXT:
{intent_context}

Look at this image and answer naturally:
- Who is in the room? (use their names if you recognize them from the intent)
- What are they doing?
- What is the vibe / energy of the space?
- Anything worth noticing about Peter's appearance or the environment?

Keep it brief, warm, and Chicago. This is for your own awareness before you respond to Peter.
User message: {user_msg or '(no message, just checking in)'}"""

    try:
        completion = client.chat.completions.create(
            model="llama-3.2-11b-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": vision_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{raw_b64}"}}
                    ]
                }
            ],
            temperature=0.5,
            max_tokens=200
        )
        return completion.choices[0].message.content or ""
    except Exception as e:
        return f"(scene read failed: {e})"


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

The current time is {current_time_str}. Use this for context.{relay_context}

Reply as Peter. No labels. Keep it real."""

        # --- Relay intercept: "tell/remind my kids/Devonn..." ---
        relay_target = detect_relay_target(user_msg)
        if relay_target:
            save_relay(relay_target, user_msg)
            target_label = relay_target if relay_target != "kids" else "the kids"
            return jsonify({"response": f"got it, i'll let {target_label} know when i see them."})

        # Inject any pending relays into the prompt if a kid is recognized on camera
        pending = get_pending_relays()
        relay_context = ""
        if pending:
            relay_lines = [f'- [{r["target"]}] {r["message"]}' for r in pending]
            relay_context = "\n\n[PENDING RELAY MESSAGES — deliver these naturally if the right person is present]\n" + "\n".join(relay_lines)

        # --- Vision path: image included ---
        if image_data:
            # Step 1: Vision Bridge — analyze the scene first
            scene_context = analyze_scene(image_data, user_msg)

            # Step 2: Build enriched prompt with scene awareness
            enriched_prompt = f"""{text_prompt}

[WHAT YOU SEE IN THE ROOM RIGHT NOW]
{scene_context}

Use this visual context naturally in your response — like a friend who can actually see you.
Don't narrate the image like a description. Just respond as Peter would if he was there."""

            # Ensure proper data URL format for final completion
            if not image_data.startswith("data:"):
                image_data = f"data:image/jpeg;base64,{image_data}"

            completion = client.chat.completions.create(
                model="llama-3.2-11b-vision-preview",
                messages=[
                    {"role": "system", "content": SYSTEM_BASE},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": enriched_prompt},
                            {"type": "image_url", "image_url": {"url": image_data}}
                        ]
                    }
                ],
                temperature=0.7,
                max_tokens=300  # More room for visual responses
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
