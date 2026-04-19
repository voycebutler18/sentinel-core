import os
from flask import Flask, request, jsonify
from groq import Groq

app = Flask(__name__)

# Use the Environment Variable we just set up
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

def load_vault():
    vault_content = ""
    # Points to the vault folder inside your sentinel_agi folder
    vault_path = "./sentinel_agi/vault"
    if not os.path.exists(vault_path):
        return "Vault path not found."
    
    for root, dirs, files in os.walk(vault_path):
        for file in files:
            with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                vault_content += f"\n--- {file} ---\n" + f.read()
    return vault_content

@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('message')
    context = load_vault()
    
    # Layer 5: The Prompt Stack
    completion = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[
            {"role": "system", "content": "You are Voyce's AGI clone. Be direct and veteran-led. Use the vault data."},
            {"role": "user", "content": f"VAULT:\n{context}\n\nCOMMAND: {user_msg}"}
        ]
    )
    return jsonify({"response": completion.choices[0].message.content})

if __name__ == "__main__":
    # Render's dynamic port assignment
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
