import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__)
CORS(app)

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

SYSTEM_INSTRUCTION = (
    "You are the digital AGI clone of Peter Butler (Voyce). "
    "You are direct, tactical, strategic, and human. "
    "Use the Vault context for all facts. "
    "Never sound like a generic assistant. "
    "Respond with clarity, confidence, and precision."
)

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction=SYSTEM_INSTRUCTION
)

def load_vault():
    vault_content = ""
    possible_paths = ["./sentinel_agi/vault", "./vault"]
    vault_path = next((p for p in possible_paths if os.path.exists(p)), None)

    if not vault_path:
        return "Critical: Vault data missing from system."

    for root, dirs, files in os.walk(vault_path):
        for file in files:
            if file.endswith((".json", ".txt", ".md")):
                try:
                    with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                        vault_content += f"\n[MEMORANDUM: {file}]\n{f.read()}\n"
                except Exception:
                    pass

    return vault_content if vault_content else "Vault is empty."

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
            return jsonify({"error": "Message is required"}), 400

        if not os.environ.get("GEMINI_API_KEY"):
            return jsonify({"error": "GEMINI_API_KEY is missing on the server"}), 500

        vault_data = load_vault()

        prompt = f"VAULT KNOWLEDGE:\n{vault_data}\n\nCOMMANDER INPUT: {user_msg}"

        response = model.generate_content(prompt)

        return jsonify({
            "response": response.text if hasattr(response, "text") else "No response generated."
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
