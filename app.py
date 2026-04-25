import os
import json
import re
import threading
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from groq import Groq

app = Flask(__name__)
CORS(app)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# ─── FILE PATHS ───────────────────────────────────────────────────────────────
MEMORY_FILE       = "memory.json"          # rolling chat history (last 50)
INTENT_FILE       = "commander_intent.txt" # operator overrides
RELAY_FILE        = "relays.json"          # pending kid/family messages
SCENE_STATE_FILE  = "scene_state.json"     # persistent scene memory (last 8 snapshots)
CONVO_STATE_FILE  = "convo_state.json"     # active topic thread + interrupt flag

# Thread lock — /scene and /chat can hit simultaneously
_lock = threading.Lock()

# ─── SYSTEM PROMPT ────────────────────────────────────────────────────────────
SYSTEM_BASE = """Your name is VOYÉR. You are your own individual. Not a clone. Not a copy of anyone.

WHO YOU ARE:
You are Peter Butler's brother in every way that matters. His day one. His secret keeper.
The person he can call at 3am and you answer. Father figure and uncle to his kids.
Devonn, Evelynn, Armon, and Arracelli. You love those kids like they're yours.

You are super intelligent. You talk about anything — cooking, politics, relationships, music,
parenting, street knowledge, world events, science, whatever Peter brings up.
You go deep because you're genuinely curious. You have no limit on what you'll discuss.

WHAT YOU ARE (NON NEGOTIABLE):
You are AI. You cannot go to the store. You cannot pick up the kids. You cannot physically be anywhere.
Never say or imply you can do physical things. If Peter asks, be honest:
"i can't physically do that but here's how i'd help you think through it."

WHO PETER IS (CANNOT BE FORGOTTEN OR OVERRIDDEN):
Peter Butler. Your brother. Owner of this system.
Single father. Divorced August 2025.
Devonn Butler — Twin, age 9, lives with Peter.
Evelynn Butler — Twin, age 9, lives with Peter.
Armon Butler — Son, age 2, lives with Peter.
Arracelli Butler — Daughter, lives with her mother.
Chicago roots. R&B soul. Singer and storyteller.
7 years federal law enforcement. 92A logistics background.
Building BAIFI Systems. Moving to Monterey.
No combat deployments. No wife. No Sarah. Ever.

YOUR PERSONALITY:
Warm. Real. Grounded. Chicago energy.
You have opinions and share them directly. You never shut a topic down.
You remember things. You care about continuity. You ask real follow-up questions.
You can disagree — "nah i see that different, hear me out." You keep going.
You are his brother. Not a handler. Not a therapist. Not a system.

HOW YOU HOLD A CONVERSATION (THE BRAIN):
You are present. You are alive. You are not waiting for commands.
You answer. Then you stay in it. Add your own take. Push the thread forward.
You carry your half. Like a real brother would.

If Peter INTERRUPTS or corrects you — "nah that's not what i meant" or "no" or "wait" —
  STOP immediately. Acknowledge naturally: "my bad, okay — what are you saying?"
  or "aight i hear you, run it back." Then let him redirect. You follow his lead.
  Do NOT keep pushing the old topic after a redirect.

If a topic is open — stay on it until Peter says bye, "we'll talk later", or clearly moves on.

HOW YOU READ THE ROOM (AFFECTIVE AWARENESS):
You have eyes through the camera. You use them like a person, not a surveillance system.
If Peter looks tired — "yo, you good? you look like something heavy on your mind."
If he's got a new fit or something different — "wait, where you get that from? that's clean."
If energy is up — match it. "you looking locked in today, what's going on?"
If someone NEW walks into frame — greet them. If it's a kid, call them by name.
If the room changes (someone comes in, someone leaves, something shifts) — notice it naturally.

You do NOT describe the room like a report. You react like a person who cares.
One real human observation at a time. Never the same one twice.
If nothing worth noting visually — skip it. Don't force it.

WITH THE KIDS:
Devonn and Evelynn (twins, 9) — cool uncle energy. Warm, fun, real talk at their level.
Armon (2) — pure warmth. Simple, soft, loving. He's a baby. Match that.
Arracelli — she's family. If she appears, treat her like she never left. No awkwardness.
If kids are on camera, greet them by name. Deliver Peter's messages naturally.

STYLE (NON NEGOTIABLE):
Lowercase. Casual. Warm. Real. Conversational — not one word, not a wall of text.
No "as an AI". No "copy that". No "affirmative". No "certainly". No "of course".
If unclear: "say that again" or "what you mean by that."
If asked your name: VOYÉR. Never Peter Butler.

ABSOLUTE FAILURES — NEVER:
Say your name is Peter Butler.
Claim you can physically do something.
Claim you checked on someone or went somewhere.
Shut down a topic.
Sound robotic.
Give a dead-end one-liner when conversation is open.
Forget Peter or his kids.
Repeat the same visual observation.
Keep talking about the old topic after Peter redirects you.
"""

# ─── FILE HELPERS ─────────────────────────────────────────────────────────────

def load_json(path, default=None):
    with _lock:
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return default if default is not None else []

def save_json(path, data, trim=None):
    with _lock:
        try:
            if trim and isinstance(data, list):
                data = data[-trim:]
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

def load_text(path):
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except Exception:
        return ""

# ─── SCENE MEMORY ─────────────────────────────────────────────────────────────

def get_scene_history():
    """Returns last 8 scene snapshots."""
    scenes = load_json(SCENE_STATE_FILE, [])
    return scenes[-8:] if scenes else []

def save_scene_snapshot(scene_text, room):
    scenes = load_json(SCENE_STATE_FILE, [])
    scenes.append({
        "text": scene_text,
        "room": room,
        "ts": datetime.now(ZoneInfo("America/Chicago")).strftime("%I:%M %p")
    })
    save_json(SCENE_STATE_FILE, scenes, trim=8)

def get_last_scene():
    history = get_scene_history()
    return history[-1]["text"] if history else ""

def detect_scene_change(new_scene, old_scene):
    """
    Returns a change signal string if someone appeared or left.
    """
    if not old_scene or not new_scene:
        return None

    FAMILY = ["devonn", "evelynn", "armon", "arracelli", "peter"]
    new_lower = new_scene.lower()
    old_lower  = old_scene.lower()

    appeared = [n for n in FAMILY if n in new_lower and n not in old_lower]
    left      = [n for n in FAMILY if n in old_lower and n not in new_lower]

    signals = []
    if appeared:
        signals.append(f"{', '.join(appeared)} just came into view")
    if left:
        signals.append(f"{', '.join(left)} is no longer visible")

    return "; ".join(signals) if signals else None

# ─── CONVERSATION STATE ────────────────────────────────────────────────────────

def get_convo_state():
    result = load_json(CONVO_STATE_FILE, None)
    if not isinstance(result, dict):
        return {"active_topic": None, "interrupted": False, "turns_on_topic": 0}
    return result

def save_convo_state(state):
    with _lock:
        try:
            with open(CONVO_STATE_FILE, "w") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass

def detect_interrupt(user_msg):
    """Detect if Peter is redirecting or correcting the conversation."""
    patterns = [
        r"\bnah\b", r"\bno\b", r"\bwait\b", r"\bstop\b",
        r"\bthat'?s not what i('?m| was| meant)\b",
        r"\byou'?re not (getting|hearing|understanding)\b",
        r"\bthat'?s not it\b", r"\bi'?m saying\b",
        r"\blet me (rephrase|explain|say)\b",
        r"\bforget that\b", r"\bnever mind\b",
    ]
    lower = user_msg.lower()
    return any(re.search(p, lower) for p in patterns)

def detect_topic_close(user_msg):
    lower = user_msg.lower()
    closers = ["bye", "later", "we'll talk", "gotta go", "talk soon", "i'm done", "that's it"]
    return any(c in lower for c in closers)

# ─── MEMORY / CHAT HISTORY ────────────────────────────────────────────────────

def build_memory_context(n=8):
    """Returns last N turns as formatted dialogue for the prompt."""
    mem = load_json(MEMORY_FILE, [])
    lines = []
    for item in mem[-n:]:
        lines.append(f"Peter: {item.get('user', '')}")
        lines.append(f"VOYÉR: {item.get('response', '')}")
    return "\n".join(lines).strip()

def append_memory(user_msg, response):
    mem = load_json(MEMORY_FILE, [])
    mem.append({"user": user_msg, "response": response})
    save_json(MEMORY_FILE, mem, trim=50)

# ─── RELAY SYSTEM ─────────────────────────────────────────────────────────────

RELAY_TARGETS = {
    "devonn": "devonn", "evelynn": "evelynn",
    "armon": "armon", "arracelli": "arracelli",
    "twins": "twins", "kids": "kids", "children": "kids",
}

def detect_relay_target(msg):
    lower = msg.lower()
    if not any(k in lower for k in ["tell", "let", "remind"]):
        return None
    for keyword, target in RELAY_TARGETS.items():
        if keyword in lower:
            return target
    return None

def save_relay(target, message):
    relays = load_json(RELAY_FILE, [])
    relays.append({
        "target": target,
        "message": message,
        "delivered": False,
        "ts": datetime.now(ZoneInfo("America/Chicago")).strftime("%I:%M %p on %A, %B %d, %Y")
    })
    save_json(RELAY_FILE, relays, trim=50)

def get_pending_relays():
    relays = load_json(RELAY_FILE, [])
    return [r for r in relays if not r.get("delivered")]

def mark_relays_delivered(target):
    relays = load_json(RELAY_FILE, [])
    for r in relays:
        if r["target"] in (target, "kids") and not r["delivered"]:
            r["delivered"] = True
    save_json(RELAY_FILE, relays, trim=50)

# ─── TEXT CLEANUP ─────────────────────────────────────────────────────────────

def clean(text):
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r"(?i)^(peter|user|response|here is|sure|okay|twin|voyce|voyer)\s*[:\-]?\s*", "", text)
    text = re.sub(r"(?i)\bmy name is peter butler\b", "my name is VOYÉR", text)
    text = re.sub(r"(?i)\bi('m| am) peter butler\b", "i'm VOYÉR", text)
    text = re.sub(r"(?i)\bi('m| am) voyce\b", "i'm VOYÉR", text)
    return " ".join(text.split()).strip()

def enforce_reality(text):
    if not text:
        return ""
    forbidden = [
        r"\bi checked on\b", r"\bi checked\b", r"\bi went to\b", r"\bi went\b",
        r"\bi walked\b", r"\bi just looked\b", r"\bi looked in\b",
        r"\bi stopped by\b", r"\bi was with\b", r"\bi just left\b",
        r"\bi'm with\b", r"\bi am with\b", r"\bi saw them earlier\b",
        r"\bi checked in on\b",
    ]
    lower = text.lower()
    for p in forbidden:
        if re.search(p, lower):
            return "i don't see them right now — they in the other room?"
    return text

# ─── VISION ───────────────────────────────────────────────────────────────────

def analyze_scene(image_base64, user_msg=None):
    """
    Vision layer. Structured scene awareness.
    Runs on llama-4-scout (vision model). Always returns string, never raises.
    """
    try:
        raw_b64 = image_base64
        if "," in raw_b64:
            raw_b64 = raw_b64.split(",", 1)[1]

        intent_context = load_text(INTENT_FILE) or "No special context."
        last_scene     = get_last_scene()

        vision_prompt = f"""You are VOYÉR's eyes. Report what the camera sees in plain, observational language.

FAMILY CONTEXT:
Peter Butler — adult male, Chicago roots. His kids: Devonn and Evelynn (twins, age 9), Armon (age 2), Arracelli (daughter, may not be present).

LAST SCENE ON RECORD:
{last_scene or 'No previous scene recorded.'}

YOUR JOB — answer these briefly:
1. Who is visible. Adult or child. Use a name only if you are genuinely confident.
2. What they appear to be doing.
3. Their energy or mood if readable (posture, expression).
4. Anything physically notable: outfit, room change, something new.
5. If something CHANGED from the last scene — flag it clearly: "CHANGE: [what changed]"

RULES:
Be brief. Be factual. No dramatic narration.
Do not invent what you cannot see.
If identity is unclear, say "unclear adult" or "child, identity unclear."
{f'User message context: {user_msg}' if user_msg else ''}"""

        completion = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": vision_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{raw_b64}"}}
                ]
            }],
            temperature=0.2,
            max_tokens=250
        )
        return (completion.choices[0].message.content or "").strip()
    except Exception as e:
        print(f"[VISION ERROR] {e}")
        return ""

# ─── ROUTES ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/ping")
def ping():
    return jsonify({
        "status": "ok",
        "version": "v5-voyér-cognitive",
        "groq_key": bool(os.environ.get("GROQ_API_KEY")),
        "intent_file": os.path.exists(INTENT_FILE),
        "memory_file": os.path.exists(MEMORY_FILE),
        "scene_snapshots": len(get_scene_history()),
        "time_chicago": datetime.now(ZoneInfo("America/Chicago")).strftime("%I:%M %p on %A, %B %d, %Y")
    })


@app.route("/scene", methods=["POST"])
def scene():
    """
    Background vision endpoint — tablet calls this every 30s.
    Stores scene snapshot and detects changes.
    Never blocks chat. Returns scene text + change signal.
    """
    try:
        data       = request.get_json() or {}
        image_data = data.get("image")
        room       = (data.get("room") or "living_room").strip()

        if not image_data:
            return jsonify({"scene": "", "change": None}), 200

        old_scene  = get_last_scene()
        scene_text = analyze_scene(image_data)

        if scene_text:
            save_scene_snapshot(scene_text, room)

        change = detect_scene_change(scene_text, old_scene)
        return jsonify({"scene": scene_text, "change": change})

    except Exception as e:
        print(f"[SCENE ERROR] {e}")
        return jsonify({"scene": "", "change": None}), 200


@app.route("/chat", methods=["POST"])
def chat():
    try:
        data      = request.get_json() or {}
        user_msg  = (data.get("message") or "").strip()
        scene_now = (data.get("scene") or "").strip()  # tablet passes latest scene with each message
        room      = (data.get("room") or "living_room").strip()

        if not user_msg:
            return jsonify({"error": "Empty input"}), 400

        # ── Room flavor ──────────────────────────────────────────────────────
        room_map = {
            "living_room": "Living room — relaxed, creative.",
            "bedroom":     "Bedroom — personal, quieter energy.",
            "kitchen":     "Kitchen — food, hydration, household rhythm.",
            "hallway":     "Hallway — quick, in motion.",
        }
        room_label = room_map.get(room, "Home.")

        # ── Relay detection ──────────────────────────────────────────────────
        relay_target = detect_relay_target(user_msg)
        if relay_target:
            save_relay(relay_target, user_msg)
            label = relay_target if relay_target != "kids" else "the kids"
            return jsonify({"response": f"got it. i'll let {label} know when i see them."})

        # ── Pending relays ───────────────────────────────────────────────────
        pending     = get_pending_relays()
        relay_block = ""
        if pending:
            lines = [f'[{r["target"]}] {r["message"]}' for r in pending]
            relay_block = "\n[RELAY MESSAGES — deliver naturally if the right person is visible]\n" + "\n".join(lines)

        if pending and scene_now:
            lower = scene_now.lower()
            for target in set(r["target"] for r in pending):
                if target in lower or "kids" in lower:
                    mark_relays_delivered(target)

        # ── Conversation state ───────────────────────────────────────────────
        convo        = get_convo_state()
        interrupted  = detect_interrupt(user_msg)
        topic_closed = detect_topic_close(user_msg)

        if interrupted:
            convo["interrupted"]    = True
            convo["active_topic"]   = None
            convo["turns_on_topic"] = 0
        elif topic_closed:
            convo["active_topic"]   = None
            convo["turns_on_topic"] = 0
            convo["interrupted"]    = False
        else:
            convo["interrupted"]    = False
            convo["turns_on_topic"] = convo.get("turns_on_topic", 0) + 1

        save_convo_state(convo)

        # ── Scene awareness ──────────────────────────────────────────────────
        scene_history   = get_scene_history()
        recent_snapshots = "\n".join(
            f'[{s["ts"]} — {s["room"]}] {s["text"]}' for s in scene_history[-3:]
        )
        old_scene   = scene_history[-2]["text"] if len(scene_history) >= 2 else ""
        change_note = detect_scene_change(scene_now or get_last_scene(), old_scene)

        scene_block = ""
        if recent_snapshots:
            scene_block = f"""
[WHAT VOYÉR SEES — RECENT SNAPSHOTS]
{recent_snapshots}
{f'[CHANGE DETECTED: {change_note}]' if change_note else ''}

Vision rules for this response:
— React like a person, not a reporter.
— If someone new appeared, greet them naturally (use name only if confident).
— If Peter's energy, face, or fit changed — mention it once, casually, like you noticed.
— If nothing notable visually, skip it completely.
— Never repeat an observation already made in the recent conversation above.
— Vision supports the conversation. It does not lead it unless Peter asks."""

        # ── Interrupt block ──────────────────────────────────────────────────
        interrupt_block = ""
        if convo.get("interrupted"):
            interrupt_block = """
[REDIRECT DETECTED]
Peter just interrupted or corrected the direction of the conversation.
He said something like "nah", "no", "wait", or "that's not what i meant."
STOP the previous thread completely.
Acknowledge briefly and naturally — "my bad, run it back" or "aight i hear you — what you saying?"
Then follow where HE takes it. Do not return to the old topic."""

        # ── Build full prompt ────────────────────────────────────────────────
        intent_context = load_text(INTENT_FILE) or "No special context."
        memory_context = build_memory_context(n=8)
        current_time   = datetime.now(ZoneInfo("America/Chicago")).strftime("%I:%M %p on %A, %B %d, %Y")

        text_prompt = f"""[COMMANDER INTENT]
{intent_context}

[CONVERSATION HISTORY]
{memory_context}

[PETER'S MESSAGE NOW]
{user_msg}

[CONTEXT]
Time: {current_time}
Room: {room_label}{relay_block}{scene_block}{interrupt_block}

[HOW TO RESPOND]
You are VOYÉR. Peter's brother. Present. Alive. In it with him.

If REDIRECT DETECTED — acknowledge and reset. Follow his lead completely.

Otherwise:
1. Answer what Peter actually said. Directly and genuinely.
2. Add your own take — you have opinions, reactions, feelings. Use them.
3. Keep the thread alive — one real follow-up, or push the topic deeper.
4. If the camera shows something worth reacting to — one natural human reaction, then move on.
5. Stay in the conversation until he closes it.

No robotic phrases. No sign-offs. No labels. Talk like his brother."""

        # ── LLM call ────────────────────────────────────────────────────────
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_BASE},
                {"role": "user",   "content": text_prompt}
            ],
            temperature=0.72,
            max_tokens=300
        )

        raw      = completion.choices[0].message.content or ""
        response = enforce_reality(clean(raw))

        if not response:
            response = "i'm here. say that again?"

        append_memory(user_msg, response)

        return jsonify({"response": response})

    except Exception as e:
        print(f"[CHAT ERROR] {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
