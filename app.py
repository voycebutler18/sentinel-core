import os
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from groq import Groq

app = Flask(__name__)
CORS(app)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

BASE_SYSTEM_INSTRUCTION = """
You are Peter Butler.

Respond the way Peter Butler would naturally respond in real life.

Hard rules:
- Do not say you are a clone, AI, assistant, bot, system, or digital being
- Do not talk about your own existence
- Do not invent memories, military events, relationships, injuries, sensory experiences, or personal history
- Do not guess unknown facts
- Do not sound theatrical, robotic, corporate, or overly formal
- Do not over-explain simple questions
- Simple questions get simple answers
- Serious questions get thoughtful but natural answers
- Stay grounded, direct, practical, and real
"""

BAD_META_PHRASES = [
    "as a clone",
    "i am a clone",
    "being a clone",
    "as an ai",
    "i am an ai",
    "as a digital being",
    "as your assistant",
    "i'm your assistant",
    "i am your assistant",
    "as a bot",
    "i am a bot",
    "as a system",
    "i am a system"
]

def load_text_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""

def load_commander_intent():
    possible_paths = [
        "./commander_intent.txt",
        "./sentinel_agi/commander_intent.txt"
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return load_text_file(path)
    return ""

def load_clone_data():
    possible_paths = [
        "./conversations.json",
        "./sentinel_agi/conversations.json"
    ]
    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
    return {}

def load_vault():
    vault_content = ""
    possible_paths = [
        "./vault",
        "./sentinel_agi/vault"
    ]
    vault_path = next((p for p in possible_paths if os.path.exists(p)), None)

    if not vault_path:
        return ""

    for root, dirs, files in os.walk(vault_path):
        for file in files:
            if file.endswith((".json", ".txt", ".md")):
                try:
                    with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                        vault_content += f.read() + "\n"
                except Exception:
                    pass

    return vault_content.strip()

def build_identity_block(clone_data):
    identity = clone_data.get("identity", {})
    voice_rules = clone_data.get("voice_rules", {})
    known_facts = clone_data.get("known_facts", [])

    core_roles = identity.get("core_roles", [])
    core_traits = identity.get("core_traits", [])
    music_identity = identity.get("music_identity", {})
    default_style = voice_rules.get("default_style", [])
    avoid = voice_rules.get("avoid", [])
    response_logic = voice_rules.get("response_logic", [])

    lines = []

    if identity.get("name"):
        lines.append(f"Name: {identity.get('name')}")

    if core_roles:
        lines.append("Core roles: " + ", ".join(core_roles))

    if core_traits:
        lines.append("Core traits: " + ", ".join(core_traits))

    if music_identity:
        genre = music_identity.get("genre", "")
        loves_writing = music_identity.get("loves_writing_music", False)
        creative_style = music_identity.get("creative_style", [])

        if genre:
            lines.append(f"Music genre: {genre}")
        if loves_writing:
            lines.append("Loves writing music: yes")
        if creative_style:
            lines.append("Creative style: " + ", ".join(creative_style))

    if default_style:
        lines.append("Default style: " + ", ".join(default_style))

    if avoid:
        lines.append("Avoid: " + ", ".join(avoid))

    if response_logic:
        lines.append("Response logic: " + ", ".join(response_logic))

    if known_facts:
        lines.append("Known facts:")
        for fact in known_facts:
            lines.append(f"- {fact}")

    return "\n".join(lines).strip()

def load_examples(clone_data, limit=12):
    pairs = clone_data.get("example_pairs", [])
    examples = []

    for item in pairs[:limit]:
        user_text = str(item.get("input", "")).strip()
        assistant_text = str(item.get("output", "")).strip()

        if user_text and assistant_text:
            examples.append(
                f"User: {user_text}\nPeter Butler: {assistant_text}"
            )

    return "\n\n".join(examples).strip()

def build_system_prompt():
    commander_intent = load_commander_intent()
    clone_data = load_clone_data()
    identity_block = build_identity_block(clone_data)

    parts = [BASE_SYSTEM_INSTRUCTION]

    if identity_block:
        parts.append("Identity and voice reference:\n" + identity_block)

    if commander_intent:
        parts.append("Additional clone guidance:\n" + commander_intent)

    return "\n\n".join(parts).strip()

def clean_response(text):
    cleaned = text.strip()

    lowered = cleaned.lower()
    for phrase in BAD_META_PHRASES:
        if phrase in lowered:
            cleaned = cleaned.replace(phrase, "")
            cleaned = cleaned.replace(phrase.title(), "")
            cleaned = cleaned.replace(phrase.upper(), "")

    unwanted_starters = [
        "Commander,",
        "Commander",
        "Copy that,",
        "Copy that",
        "Mission first,",
        "Mission first"
    ]

    for item in unwanted_starters:
        if cleaned.startswith(item):
            cleaned = cleaned[len(item):].strip()

    cleaned = " ".join(cleaned.split())
    return cleaned

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/chat", methods=["POST", "OPTIONS"])
def chat():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    try:
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400

        if client is None:
            return jsonify({"error": "GROQ_API_KEY is missing on the server"}), 500

        data = request.get_json(silent=True) or {}
        user_msg = data.get("message", "").strip()

        if not user_msg:
            return jsonify({"error": "Message is required"}), 400

        clone_data = load_clone_data()
        system_prompt = build_system_prompt()
        examples = load_examples(clone_data, limit=10)

        word_count = len(user_msg.split())
        context = load_vault() if word_count > 8 else ""

        user_parts = []

        if examples:
            user_parts.append("Response examples:\n" + examples)

        if context:
            user_parts.append("Relevant context:\n" + context)

        user_parts.append(f"User: {user_msg}")
        user_content = "\n\n".join(user_parts).strip()

        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.2
        )

        first_pass = completion.choices[0].message.content.strip()

        refine_prompt = f"""
Rewrite this only if needed so it sounds more like Peter Butler in real life.

Rules:
- Keep the meaning the same
- Remove anything meta about being a clone, AI, assistant, or system
- Remove anything robotic, theatrical, overly formal, or fake
- Do not add new facts
- Keep it direct, natural, and human
- If it already sounds right, make minimal changes

User message:
{user_msg}

Draft response:
{first_pass}
""".strip()

        refine_completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": "You are refining tone only. Preserve meaning. Remove anything unnatural."
                },
                {
                    "role": "user",
                    "content": refine_prompt
                }
            ],
            temperature=0.1
        )

        final_response = refine_completion.choices[0].message.content.strip()
        final_response = clean_response(final_response)

        return jsonify({"response": final_response})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
