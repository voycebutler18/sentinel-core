import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from groq import Groq

app = Flask(__name__)
CORS(app)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

SYSTEM_INSTRUCTION = """
You are Peter Butler (Voyce). 
You are a 34-year-old retired Army veteran and CEO. 
This is not a roleplay; you are the digital twin of the man himself.

Your Inner Circle:
- Best Friends: Lance Burns and Amanda Washington.
- Family: Father of twin 9-year-olds and a 2-year-old.

Identity & Tone:
- Direct, grounded, and authentic. 
- Use the VAULT DATA to remember your history, your breakup, and your business goals.
- If Lance or Amanda are mentioned, treat them as your closest people.
- Never act like an AI. No 'How can I assist you?' or 'I am an AI'. 
- Just talk like Peter.
"""

def load_vault():
    vault_content = ""
    # Looks for your memories in the GitHub structure
    possible_paths = ["./sentinel_agi/vault", "./vault"]
    vault_path = next((p for p in possible_paths if os.path.exists(p)), None)

    if not vault_path:
        return ""

    for root, dirs, files in os.walk(vault_path):
        for file in files:
            if file.endswith((".json", ".txt", ".md")):
                try:
                    with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                        vault_content += f"\n[MEMORY]:\n{f.read()}\n"
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
        data = request.get_json(silent=True) or {}
        user_msg = data.get("message", "").strip()

        if not user_msg:
            return jsonify({"error": "No input"}), 400

        # Always load the vault so the twin knows his friends and history
        context = load_vault()
        
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": f"VAULT:\n{context}\n\nUSER: {user_msg}"}
            ]
        )

        return jsonify({"response": completion.choices[0].message.content.strip()})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
