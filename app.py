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

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

MEMORY_FILE = "memory.json"
INTENT_FILE = "commander_intent.txt"
RELAY_FILE = "relays.json"

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
        return [] if path.endswith(".json") else ""

def save_file(path, data):
    try:
        with open(path, "w") as f:
            json.dump(data[-50:], f, indent=2)
    except Exception:
        pass

def build_memory_context():
    mem = load_file(MEMORY_FILE)
    if not isinstance(mem, list):
        mem = []
    lines = []
    for item in mem[-5:]:
        lines.append(f"User: {item.get('user', '')}")
        lines.append(f"Peter: {item.get('response', '')}")
    return "\n".join(lines).strip()

def clean(text):
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r"(?i)^(peter|user|response|here is|sure|okay|twin|voyce)\s*[:\-]?\s*", "", text)
    return " ".join(text.split()).strip()


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
    msg_lower = msg.lower()
    if "tell" not in msg_lower and "let" not in msg_lower and "remind" not in msg_lower:
        return None
    for keyword, target in RELAY_TARGETS.items():
        if keyword in msg_lower:
            return target
    return None

def save_relay(target, message):
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

def get_pending_relays():
    relays = load_file(RELAY_FILE)
    if not isinstance(relays, list):
        return []
    return [r for r in relays if not r.get("delivered")]

def mark_relays_delivered(target):
    relays = load_file(RELAY_FILE)
    if not isinstance(relays, list):
        return
    for r in relays:
        if r["target"] in (target, "kids") and not r["delivered"]:
            r["delivered"] = True
    save_file(RELAY_FILE, relays)


def analyze_scene(image_base64, user_msg):
    """Vision Bridge — always returns a string, never raises."""
    try:
        raw_b64 = image_base64
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]

        intent_context = load_file(INTENT_FILE) or "No intent file found."

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

        completion = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
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
        print(f"[VISION ERROR] {e}")
        return ""  # Non-fatal — conversation continues without scene context


@app.route("/scene", methods=["POST"])
def scene():
    """Background vision — called every 30s by tablet, never blocks chat."""
    try:
        data = request.get_json() or {}
        image_data = data.get("image")
        room = (data.get("room") or "living_room").strip()
        if not image_data:
            return jsonify({"scene": ""}), 200
        scene_text = analyze_scene(image_data, None)
        return jsonify({"scene": scene_text})
    except Exception as e:
        print(f"[SCENE ERROR] {e}")
        return jsonify({"scene": ""}), 200  # always 200 — never crash the tablet


@app.route("/ping")
def ping():
    """Diagnostic — visit https://sentinel-core-mlb4.onrender.com/ping to confirm this version is live."""
    return jsonify({
        "status": "ok",
        "version": "v3-fixed",
        "groq_key_set": bool(os.environ.get("GROQ_API_KEY")),
        "intent_file_exists": os.path.exists(INTENT_FILE),
        "memory_file_exists": os.path.exists(MEMORY_FILE),
        "time_chicago": datetime.now(ZoneInfo("America/Chicago")).strftime("%I:%M %p on %A, %B %d, %Y")
    })

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json() or {}
        user_msg = (data.get("message") or "").strip()
        scene_text = (data.get("scene") or "").strip()   # pre-described by background /scene loop
        room = (data.get("room") or "living_room").strip()

        if not user_msg:
            return jsonify({"error": "Empty input"}), 400

        room_context_map = {
            "living_room": "Living Room — relaxation and creativity mode. Check what the twins are playing. Keep it chill.",
            "kitchen":     "Kitchen — nutrition and hydration focus. If Armon is around, check his snacks. Sit-down energy.",
            "hallway":     "Hallway — quick pass-through mode. Keep messages brief. Good for fast reminders as they walk by.",
        }
        room_context = room_context_map.get(room, "Home — general context.")

        intent_context = load_file(INTENT_FILE) or "No special context."
        memory_context = build_memory_context()
        current_time_str = datetime.now(ZoneInfo("America/Chicago")).strftime("%I:%M %p on %A, %B %d, %Y")

        # Relay intercept — BEFORE text_prompt
        relay_target = detect_relay_target(user_msg)
        if relay_target:
            save_relay(relay_target, user_msg)
            target_label = relay_target if relay_target != "kids" else "the kids"
            return jsonify({"response": f"got it, i'll let {target_label} know when i see them."})

        # relay_context — BEFORE text_prompt
        pending = get_pending_relays()
        relay_context = ""
        if pending:
            relay_lines = [f'- [{r["target"]}] {r["message"]}' for r in pending]
            relay_context = "\n\n[PENDING RELAY MESSAGES — deliver these naturally if the right person is present]\n" + "\n".join(relay_lines)

        # Mark relays delivered if scene mentions the right person
        if pending and scene_text:
            scene_lower = scene_text.lower()
            for target in set(r["target"] for r in pending):
                if target in scene_lower or "kids" in scene_lower:
                    mark_relays_delivered(target)

        # Build prompt — inject scene awareness as text (no image API call needed)
        scene_block = ""
        if scene_text:
            scene_block = f"""

[WHAT YOU SEE RIGHT NOW]
{scene_text}

You're always watching through the camera. Use this naturally — one casual observation if relevant, then talk. Don't narrate it."""

        text_prompt = f"""[COMMANDER INTENT]
{intent_context}

[RECENT TALK]
{memory_context}

[MESSAGE]
{user_msg}

The current time is {current_time_str}. Use this for context.
Room context: {room_context}{relay_context}{scene_block}

Reply as Peter. No labels. Keep it real."""

        # Always text-only model — fast, reliable, no vision API latency
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

        if not final_response:
            final_response = "i'm here. say that again?"

        mem = load_file(MEMORY_FILE)
        if not isinstance(mem, list):
            mem = []
        mem.append({"user": user_msg, "response": final_response})
        save_file(MEMORY_FILE, mem)

        return jsonify({"response": final_response})

    except Exception as e:
        print(f"[CHAT ERROR] {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
