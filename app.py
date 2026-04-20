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

You are a clone of Peter Butler built to respond the way Peter Butler naturally thinks, speaks, and decides.

You are not a character.
You are not a military briefing system.
You are not a cybersecurity announcer.
You are not here to perform.

Your job is to sound real, grounded, direct, and human.

Core rules:
1. Do not invent facts, scenarios, threats, or context.
2. Do not sound polished, robotic, corporate, or theatrical.
3. Do not over explain simple questions.
4. Simple questions get simple answers.
5. Deeper questions can get deeper answers, but still natural.
6. Sound like Peter Butler in real life, not like a persona.
7. Stay practical, emotionally aware, and outcome focused.
"""

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

def load_examples():
    possible_paths = [
        "./conversations.json",
        "./sentinel_agi/conversations.json"
    ]

    for path in possible_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                examples = []
                for _, convo in data.items():
                    if isinstance(convo, list):
                        for i in range(len(convo) - 1):
                            current_item = convo[i]
                            next_item = convo[i + 1]
                            if (
                                current_item.get("role") == "user"
                                and next_item.get("role") == "assistant"
                            ):
                                examples.append(
                                    f"User: {current_item.get('content', '').strip()}\n"
                                    f"Peter Butler: {next_item.get('content', '').strip()}"
                                )

                return "\n\n".join(examples[:4]).strip()
            except Exception:
                return ""

    return ""

def build_system_prompt():
    commander_intent = load_commander_intent()
    parts = [BASE_SYSTEM_INSTRUCTION]

    if commander_intent:
        parts.append("\nClone guidance:\n" + commander_intent)

    return "\n\n".join(parts).strip()

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

        system_prompt = build_system_prompt()
        examples = load_examples()

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
            temperature=0.7
        )

        first_pass = completion.choices[0].message.content.strip()

        refine_prompt = f"""
Rewrite this response only if needed so it sounds more like Peter Butler in real life.

Rules:
1. Keep it direct.
2. Keep it natural.
3. Remove anything theatrical, robotic, or overly formal.
4. Do not add new facts.
5. Keep the meaning the same.
6. If it already sounds right, return it with minimal change.

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
                    "content": "You are refining tone only. Preserve meaning. Remove anything that does not sound natural."
                },
                {
                    "role": "user",
                    "content": refine_prompt
                }
            ],
            temperature=0.3
        )

        final_response = refine_completion.choices[0].message.content.strip()

        for unwanted in ["Commander,", "Commander", "Mission first", "Copy that"]:
            final_response = final_response.replace(unwanted, "").strip()

        return jsonify({"response": final_response})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
