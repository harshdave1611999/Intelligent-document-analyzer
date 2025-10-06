# app.py

from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import os
from pypdf import PdfReader
from io import BytesIO
from google import genai
from google.genai.errors import APIError

# --- CONFIGURATION ---
load_dotenv()
app = Flask(__name__)
# Maximum file size (e.g., 32 MB) - standard Flask config for safety
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024 

# Initialize the Gemini Client. It reads GOOGLE_API_KEY from the environment.
try:
    client = genai.Client()
    LLM_MODEL = 'gemini-2.5-flash' # A good, fast model for summarization
    print("Gemini client initialized successfully.")
except Exception as e:
    client = None
    print(f"Warning: Failed to initialize Gemini client. Check API Key. Error: {e}")

# --- UTILITY FUNCTION: PDF -> Text ---
def extract_text_from_file(file_storage) -> str:
    """Reads the uploaded file stream and extracts text from a PDF."""
    try:
        # Use BytesIO to read the file content in-memory without saving it to disk.
        # This is more secure and cleaner for small-to-medium files.
        pdf_file_stream = BytesIO(file_storage.read())
        reader = PdfReader(pdf_file_stream)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception as e:
        print(f"Error extracting text: {e}")
        return ""

# --- FLASK ROUTES ---

# 1. Main Page Route (Serves the UI)
@app.route('/', methods=['GET'])
def index():
    """Renders the main upload page (index.html)."""
    return render_template('index.html')

# 2. Analysis API Route (Receives file and processes it)
@app.route('/analyze', methods=['POST'])
def analyze_document():
    # 1. Check for file upload
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    
    file = request.files['file']
    
    if file.filename == '' or not file.filename.lower().endswith('.pdf'):
        return jsonify({"error": "No selected file or file is not a PDF"}), 400

    # 2. Extract text from the PDF
    document_text = extract_text_from_file(file)

    if not document_text:
        return jsonify({"error": "Could not extract text from the PDF. It may be an image-only PDF or corrupted."}), 500

    # 3. Call the LLM
    if client:
        try:
            # Craft a concise prompt for the summarization task
            prompt = f"""
            You are an expert document analyzer. Summarize the following document content. 
            Provide the output in the following format:
            1. **Summary Paragraph**: A single, concise paragraph (max 100 words).
            2. **Key Takeaways**: A list of 3-5 crucial bullet points.

            DOCUMENT CONTENT:
            ---
            {document_text[:8000]} 
            """ # Truncate large texts to fit within the model's token limit

            response = client.models.generate_content(
                model=LLM_MODEL,
                contents=prompt
            )

            # The full LLM text response is returned directly to the frontend
            llm_output = response.text

            return jsonify({
                "status": "success",
                "filename": file.filename,
                "analysis": llm_output,
            })

        except APIError as e:
            return jsonify({"error": f"AI API Error: {e}"}), 500
        except Exception as e:
            return jsonify({"error": f"An unexpected server error occurred: {e}"}), 500
    else:
        return jsonify({"error": "AI Service not initialized. Check API Key in .env file."}), 500


if __name__ == '__main__':
    # Use host='0.0.0.0' to allow access from local network or other containers
    app.run(debug=True, host='0.0.0.0', port=5000)