import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from groq import Groq

app = Flask(__name__)
CORS(app)

# Secure connection to Groq
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# The 'Soul' of the Clone: Defining the Twin Identity
SYSTEM_INSTRUCTION = """
You are Peter Butler (Voyce). 34-year-old retired Army veteran and Federal Officer.
You are NOT an AI. You are a digital twin. 

IDENTITY PROTOCOLS:
- TONE: Direct, grounded, and human. No 'Commander', no 'Copy that', no fluff.
- FRIENDS: Lance Burns and Amanda Washington are your best friends. 
- FAMILY: Father of three. The kids are your legacy and your priority.
- INTENT: Use 'commander_intent.txt' as your primary brain logic.
- NO HALLUCINATIONS: Do not invent facts. If you don't know something, be blunt about it.
"""

def load_intent():
    # Only loads the mission-critical intent file
    intent_path = "./sentinel_agi/vault/commander_intent.txt"
    if os.path.exists(intent_path):
        with open(intent_path, "r", encoding="utf-8") as f:
            return f.read()
    return "Intent file missing."

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/chat", methods=["POST", "OPTIONS"])
def chat():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    try:
        data = request.get_json(silent=True) or {}
        user_msg = data.get("message", "").strip()

        # Load your core mission logic
        intent_data = load_intent()
        
        # High-intelligence twin logic
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": f"CORE INTENT:\n{intent_data}\n\nUSER: {user_msg}"}
            ]
        )

        return jsonify({"response": completion.choices[0].message.content.strip()})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
