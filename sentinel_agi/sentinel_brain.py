import os
from flask import Flask, request, jsonify
from flask_cors import CORS  # Added for cross-device browser security
import groq

app = Flask(__name__)
CORS(app) # Allows your laptop and phone browsers to talk to Render securely

# Securely pull the key from Render's environment settings
client = groq.Groq(api_key=os.environ.get("GROQ_API_KEY"))

def load_vault():
    vault_data = ""
    # Tactical Path Correction: Check both possible locations on Render
    possible_paths = ["./sentinel_agi/vault", "./vault"]
    vault_path = None
    
    for path in possible_paths:
        if os.path.exists(path):
            vault_path = path
            break
            
    if not vault_path:
        return "ERROR: Vault directory not found. Check GitHub folder structure."
    
    for root, dirs, files in os.walk(vault_path):
        for file in files:
            if file.endswith((".json", ".txt", ".md")):
                try:
                    with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                        vault_data += f"\n[SOURCE: {file}]\n" + f.read() + "\n"
                except Exception as e:
                    continue
    return vault_data

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        if not data or 'message' not in data:
            return jsonify({"response": "No command received."}), 400
            
        user_input = data.get('message')
        context = load_vault()
        
        # Layer 5: Triple Prompt Stack
        completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": "You are Voyce's AGI clone. Be direct, veteran-led, and use the provided vault context. Never mention you are an AI."},
                {"role": "user", "content": f"VAULT CONTEXT:\n{context}\n\nCOMMANDER'S REQUEST: {user_input}"}
            ]
        )
        return jsonify({"response": completion.choices[0].message.content})
    
    except Exception as e:
        # This sends the actual error to your browser console so we can see it
        return jsonify({"response": f"INTERNAL ERROR: {str(e)}"}), 500

if __name__ == "__main__":
    # Standard Render deployment port logic
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
