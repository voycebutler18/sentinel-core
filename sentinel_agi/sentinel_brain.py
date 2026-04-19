import os
from flask import Flask, request, jsonify
from groq import Groq

app = Flask(__name__)
# Securely pull your API key (add this to GitHub Secrets later)
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

def load_vault():
    vault_content = ""
    # Scans the /vault folder you just uploaded
    for root, dirs, files in os.walk("./sentinel_agi/vault"):
        for file in files:
            with open(os.path.join(root, file), 'r') as f:
                vault_content += f"\n--- {file} ---\n" + f.read()
    return vault_content

@app.route('/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('message')
    context = load_vault()
    
    # Layer 5: Triple Prompt Stack
    completion = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[
            {"role": "system", "content": "You are Voyce's AGI clone. Be direct and veteran-led."},
            {"role": "user", "content": f"VAULT:\n{context}\n\nUSER: {user_msg}"}
        ]
    )
    return jsonify({"response": completion.choices[0].message.content})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
