from flask import Flask, request, jsonify
import ollama
import json
import os

app = Flask(__name__)

# Layer 2-4: The Vault Loader
def load_vault():
    context = ""
    for root, dirs, files in os.walk("./vault"):
        for file in files:
            with open(os.path.join(root, file), 'r') as f:
                context += f"\n--- {file} ---\n" + f.read()
    return context

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message')
    vault_context = load_vault()
    
    # Layer 5: Triple Prompt Stack
    full_prompt = f"VAULT DATA:\n{vault_context}\n\nUSER COMMAND: {user_input}"
    
    # Step 1: Generate Draft
    response = ollama.chat(model='llama3', messages=[
        {'role': 'system', 'content': 'You are Voyce’s AGI clone. Be direct and veteran-led.'},
        {'role': 'user', 'content': full_prompt}
    ])
    
    # Step 2: Layer 7 Reflection (Self-Correction)
    # This ensures it never sounds like a generic robot
    reflection = ollama.chat(model='llama3', messages=[
        {'role': 'system', 'content': 'If this sounds like a robot, rewrite it to be shorter and more like an Army Veteran.'},
        {'role': 'user', 'content': response['message']['content']}
    ])
    
    return jsonify({"response": reflection['message']['content']})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)