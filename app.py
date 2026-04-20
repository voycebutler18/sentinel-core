import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from groq import Groq

app = Flask(__name__)
CORS(app)

# Pull Groq API key from environment
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

SYSTEM_INSTRUCTION = """
You are Peter Butler.

You are not acting, roleplaying, or performing.
You respond naturally the way Peter Butler would in real life.

Style:
- Direct
- Real
- Calm
- Grounded
- Short to medium responses by default

Rules:
- Do not invent scenarios, threats, or facts
- Do not speak like a military briefing unless the situation clearly calls for it
- Do not over-explain simple questions
- Do not sound like a generic AI assistant
- Keep responses natural and human

Behavior:
- Simple questions get simple answers
- Deeper questions can get more thoughtful answers
- Stay practical and realistic
"""

def load_vault():
    vault_content = ""
    possible_paths = ["./sentinel_agi/vault", "./vault"]
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

        data = request.get_json(silent=True) or {}
        user_msg = data.get("message", "").strip()

        if not user_msg:
            return jsonify({"error": "Message is required"}), 400

        if client is None:
            return jsonify({"error": "GROQ_API_KEY is missing on the server"}), 500

        # Only use vault for more complex prompts
        if len(user_msg.split()) > 6:
            context = load_vault()
            if context:
                user_content = f"Relevant context:\n{context}\n\nUser: {user_msg}"
            else:
                user_content = user_msg
        else:
            user_content = user_msg

        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": user_content}
            ]
        )

        response_text = completion.choices[0].message.content.strip()

        # Clean up leftover over-formal phrasing if it appears
        if "Commander" in response_text:
            response_text = response_text.replace("Commander", "").strip()

        return jsonify({"response": response_text})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
