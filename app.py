import os
from flask import Flask, request, jsonify
from groq import Groq

app = Flask(__name__)
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

def load_vault():
    vault_content = ""
    vault_path = "./sentinel_agi/vault"
    if not os.path.exists(vault_path):
        return "No vault data found."
    for root, dirs, files in os.walk(vault_path):
        for file in files:
            if file.endswith((".txt", ".json", ".md")):
                try:
                    with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                        vault_content += f"\n--- {file} ---\n" + f.read()
                except Exception:
                    pass
    return vault_content if vault_content else "Vault is empty."

@app.route('/')
def index():
    return "SENTINEL ONLINE", 200

@app.route('/chat', methods=['POST', 'OPTIONS'])
def chat():
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        return response

    user_msg = request.json.get('message', '')
    context = load_vault()

    completion = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[
            {"role": "system", "content": "You are Voyce's personal AGI — direct, veteran-led, and strategic. Use the vault data to personalize every response."},
            {"role": "user", "content": f"VAULT:\n{context}\n\nCOMMAND: {user_msg}"}
        ]
    )

    response = jsonify({"response": completion.choices[0].message.content})
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
