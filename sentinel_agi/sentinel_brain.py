import os
from flask import Flask, request, jsonify
import groq # You will need to add 'groq' to your requirements.txt

app = Flask(__name__)

# Securely pull the key from Render's environment settings
client = groq.Groq(api_key=os.environ.get("GROQ_API_KEY"))

def load_vault():
    vault_data = ""
    vault_path = "./sentinel_agi/vault" # Path matching your GitHub structure
    if not os.path.exists(vault_path):
        return "Vault connection lost."
    for root, dirs, files in os.walk(vault_path):
        for file in files:
            if file.endswith((".json", ".txt")):
                with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                    vault_data += f.read() + "\n"
    return vault_data

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message')
    context = load_vault()
    
    # Layer 5: Triple Prompt Stack (Identity + Context + Mission)
    completion = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[
            {"role": "system", "content": "You are Voyce's AGI clone. Use the vault context. Be direct and veteran-led."},
            {"role": "user", "content": f"CONTEXT:\n{context}\n\nCOMMAND: {user_input}"}
        ]
    )
    return jsonify({"response": completion.choices[0].message.content})

if __name__ == "__main__":
    # Render requires the app to run on port 10000 by default
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
