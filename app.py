import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from groq import Groq  # Back to the specialist engine

app = Flask(__name__)
CORS(app)

# Pulls the Groq key from Render's environment
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

SYSTEM_INSTRUCTION = (
    "You are Peter Butler (Voyce). 34-year-old Army Veteran and CEO. "
    "You are tactical, direct, and human. Use your vault context. "
    "Never act like an AI. You are the Commander."
)

def load_vault():
    vault_content = ""
    vault_path = "./sentinel_agi/vault"
    if not os.path.exists(vault_path): return "Vault connection lost."
    
    for root, dirs, files in os.walk(vault_path):
        for file in files:
            if file.endswith((".json", ".txt", ".md")):
                with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                    vault_content += f.read() + "\n"
    return vault_content

@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/chat", methods=["POST"])
def chat():
    try:
        user_msg = request.json.get("message")
        context = load_vault()
        
        # Using the Llama 3.1 8B model for high-volume free access
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": f"VAULT:\n{context}\n\nCOMMAND: {user_msg}"}
            ]
        )
        return jsonify({"response": completion.choices[0].message.content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
