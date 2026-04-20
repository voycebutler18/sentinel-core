import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__)
CORS(app) # Ensures your browser connection remains stable

# Securely pulls the Gemini key from Render's environment
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# Instruction Layer: This defines the "Super Smart Peter Butler"
SYSTEM_INSTRUCTION = (
    "You are the digital AGI clone of Peter Butler (Voyce). "
    "You are a 34-year-old retired Army veteran and Federal Police Officer. "
    "You are the CEO of BAIFI Systems and a father of three. "
    "Your tone is direct, tactical, and high-stakes. Use the Vault context for all facts. "
    "NEVER act like a generic assistant. You ARE Peter Butler."
)

# FIXED: Removed the double 'model=' definition and updated to the stable 2.5 model
model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    system_instruction=SYSTEM_INSTRUCTION
)

def load_vault():
    vault_content = ""
    # Checks both GitHub subfolder and Render root path
    possible_paths = ["./sentinel_agi/vault", "./vault"]
    vault_path = next((p for p in possible_paths if os.path.exists(p)), None)
    
    if not vault_path:
        return "Critical: Vault data missing from system."
    
    for root, dirs, files in os.walk(vault_path):
        for file in files:
            if file.endswith((".json", ".txt", ".md")):
                try:
                    with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                        vault_content += f"\n[MEMORANDUM: {file}]\n{f.read()}\n"
                except Exception:
                    continue
    return vault_content

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        if not data or 'message' not in data:
            return jsonify({"response": "No command received."}), 400
            
        user_msg = data.get('message')
        vault_data = load_vault()
        
        # Injects the entire vault directly into the prompt
        prompt = f"VAULT KNOWLEDGE:\n{vault_data}\n\nCOMMANDER INPUT: {user_msg}"
        
        response = model.generate_content(prompt)
        return jsonify({"response": response.text})
    except Exception as e:
        # Prints actual error to Render logs for easier debugging
        print(f"Error: {str(e)}")
        return jsonify({"response": f"System Alert: {str(e)}"}), 500

if __name__ == "__main__":
    # Dynamic port for Render deployment
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
