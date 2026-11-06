import os
import sqlite3
import ast
import math
from collections import Counter
import re
import time
import torch
import faiss
import numpy as np
import gradio as gr
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import whisper
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    BitsAndBytesConfig,
    M2M100ForConditionalGeneration,
    M2M100Tokenizer
)
from sentence_transformers import SentenceTransformer
from diffusers import StableDiffusionPipeline

device = "cuda" if torch.cuda.is_available() else "cpu"

# =====================================================================
# 1. DATABASE & INITIALIZATION
# =====================================================================
conn = sqlite3.connect("eduvision.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS checkins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        role TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.commit()

# Knowledge Base for RAG System
DEFAULT_DOCS = [
    {"id": "doc1", "title": "Eduvision Architecture", "content": "Eduvision AI Suite integrates core modules for automated learning paths, adaptive assessments, and real-time analytics. Built with FastAPI backend, SQLite database, and Gradio interface hosted on Render."},
    {"id": "doc2", "title": "DevBot Code Engine", "content": "DevBot generates production-ready code modules, performs Python syntax validation using abstract syntax trees, and refactors legibility."},
    {"id": "doc3", "title": "DesignBot UI System", "content": "DesignBot produces dynamic responsive layout specifications, Tailwind CSS components, React components, and enterprise UI designs."},
    {"id": "doc4", "title": "Secure Check-In Verification", "content": "Secure Check-In manages role-based access logging and tracks real-time check-in analytics stored persistently."}
]

# =====================================================================
# 2. MODEL INITIALIZATION (SHARED LLM & EMBEDDINGS)
# =====================================================================
print("[System] Initializing Speech-To-Text (Whisper Base)...")
whisper_model = whisper.load_model("base", device=device)

print("[System] Initializing Cross-Lingual Preprocessor (M2M100)...")
PREPROCESS_MODEL = "facebook/m2m100_418M"
m2m_tokenizer = M2M100Tokenizer.from_pretrained(PREPROCESS_MODEL)
m2m_model = M2M100ForConditionalGeneration.from_pretrained(
    PREPROCESS_MODEL,
    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
).to(device)

print("[System] Initializing 4-bit Quantized LLM (Qwen2.5-1.5B)...")
MODEL_ID = "Qwen/Qwen2.5-1.5B-Instruct"
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16
)
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    quantization_config=bnb_config,
    device_map="auto"
)

print("[System] Initializing LaBSE Embedding Model...")
embedder = SentenceTransformer('sentence-transformers/laBSE', device=device)

print("[System] Initializing Stable Diffusion Pipeline with CPU Offloading...")
try:
    sd_pipeline = StableDiffusionPipeline.from_pretrained(
        "runwayml/stable-diffusion-v1-5",
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
    )
    sd_pipeline.enable_model_cpu_offload()
except Exception as e:
    print(f"Stable Diffusion loading warning: {e}")
    sd_pipeline = None

# Heritage & Bengali Literature Corpus Setup for Anant
heritage_corpus = [
    "ধর্মক্ষেত্রে কুরুক্ষেত্রে সমবেতা যুযুত্সবঃ। মামকাঃ পাণ্ডবাশ্চৈব কিমকুর্বত সঞ্জয়॥",
    "প্রথমে প্রণমি হরি বিশ্বচরাচর। যাহা হইতে প্রকাশ পায় এ চরাচর॥",
    "সাধু ভাষা ও উচ্চাঙ্গ সাহিত্যের জ্ঞানচর্চার জন্য এই অনন্ত-দ্য ক্যান্টর ইন্টেলিজেন্স ইঞ্জিন প্রস্তুত করা হইয়াছে।",
    "মহাকবি কিরাতাপরশুরাম ও ব্যাসদেব মহাভারতের মহাকাব্য রচনা করিয়া ভারতের সনাতন ধর্মচেতনাকে রূপদান করিয়াছিলেন।",
    "শ্রীমদ্ভগবদ্গীতা মহাভারতের ভীষ্মপর্বের অন্তর্গত একটি প্রধান ধর্মীয় ও দার্শনিক গ্রন্থ।"
]

corpus_embeddings = embedder.encode(heritage_corpus, convert_to_numpy=True)
anant_index = faiss.IndexFlatL2(corpus_embeddings.shape[1])
anant_index.add(corpus_embeddings)

print(f"✓ All Models Fully Initialized!\n")

# =====================================================================
# 3. FEATURE HANDLERS
# =====================================================================

# --- MODULE 1: Secure Check-In ---
def process_checkin(name, role):
    if not name or not name.strip():
        return "⚠️ Please provide a valid name.", get_recent_checkins(), get_checkin_stats()
    
    cursor.execute("INSERT INTO checkins (name, role) VALUES (?, ?)", (name, role))
    conn.commit()
    return f"✅ Secure Check-In successful for {name} ({role})!", get_recent_checkins(), get_checkin_stats()

def clear_checkins():
    cursor.execute("DELETE FROM checkins")
    conn.commit()
    return "🗑️ Check-in database logs reset.", get_recent_checkins(), get_checkin_stats()

def get_recent_checkins():
    cursor.execute("SELECT id, name, role, timestamp FROM checkins ORDER BY timestamp DESC LIMIT 15")
    rows = cursor.fetchall()
    return rows if rows else []

def get_checkin_stats():
    cursor.execute("SELECT COUNT(*) FROM checkins")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT role, COUNT(*) FROM checkins GROUP BY role")
    by_role = cursor.fetchall()
    role_summary = ", ".join([f"{r[0]}: {r[1]}" for r in by_role]) if by_role else "No entries"
    return f"**Total Check-Ins:** {total}  |  **By Role:** {role_summary}"


# --- MODULE 2: Eduvision-RAGBot (Conventional Conversational Answer) ---
def tokenize(text):
    return re.findall(r'\w+', text.lower())

def run_ragbot(query, custom_doc=""):
    if not query or not query.strip():
        return "⚠️ Please enter a query."

    documents = list(DEFAULT_DOCS)
    if custom_doc and custom_doc.strip():
        documents.append({"id": "custom1", "title": "User Uploaded Doc", "content": custom_doc.strip()})

    corpus = [doc["content"] for doc in documents]
    all_tokens = set(token for text in corpus + [query] for token in tokenize(text))
    
    def get_vector(text):
        tokens = tokenize(text)
        counts = Counter(tokens)
        return [counts[word] for word in all_tokens]

    def cosine_similarity(v1, v2):
        dot = sum(a * b for a, b in zip(v1, v2))
        mag1 = math.sqrt(sum(a * a for a in v1))
        mag2 = math.sqrt(sum(b * b for b in v2))
        if not mag1 or not mag2:
            return 0.0
        return dot / (mag1 * mag2)

    query_vec = get_vector(query)
    scores = []
    
    for doc in documents:
        doc_vec = get_vector(doc["content"])
        score = cosine_similarity(query_vec, doc_vec)
        scores.append((score, doc))

    scores.sort(key=lambda x: x[0], reverse=True)
    best_score, top_doc = scores[0] if scores else (0.0, {"title": "General", "content": "No documents found."})

    retrieved_context = top_doc["content"] if best_score > 0.03 else "No direct matching document found in the knowledge base."

    # Use Qwen LLM to synthesize a natural, conventional conversational answer
    rag_prompt = (
        f"<|im_start|>system\nYou are Eduvision RAGBot, an enterprise AI assistant. "
        f"Provide a natural, conventional, and helpful answer to the user based on the retrieved context.\n"
        f"[Context]: {retrieved_context}<|im_end|>\n"
        f"<|im_start|>user\n{query}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )

    inputs = tokenizer(rag_prompt, return_tensors="pt").to(device)
    with torch.inference_mode():
        outputs = model.generate(
            **inputs,
            max_new_tokens=250,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id
        )
    
    answer = tokenizer.decode(outputs[0][inputs.input_ids.shape[-1]:], skip_special_tokens=True).strip()
    return answer


# --- MODULE 3: Eduvision-DevBot (Code Generator & AST Syntax Checker) ---
def run_devbot(prompt, task_type):
    if not prompt or not prompt.strip():
        return "# Please enter a valid task prompt.", "⚠️ No code to evaluate."

    if task_type == "FastAPI Endpoint":
        code = f'''# Auto-generated FastAPI Endpoint
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Eduvision API")

class Payload(BaseModel):
    query: str
    user_id: int = 1

@app.post("/api/v1/{prompt.lower().replace(' ', '_')}")
async def handle_request(payload: Payload):
    """Handler for {prompt}"""
    if not payload.query:
        raise HTTPException(status_code=400, detail="Query string cannot be empty")
    return {{"status": "success", "processed": payload.query, "user": payload.user_id}}
'''
    elif task_type == "SQLite CRUD":
        code = f'''# Auto-generated SQLite Database Module
import sqlite3

class DatabaseManager:
    def __init__(self, db_name="{prompt.lower().replace(' ', '_')}.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.setup()

    def setup(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def insert(self, data: str):
        self.cursor.execute("INSERT INTO records (data) VALUES (?)", (data,))
        self.conn.commit()
'''
    else:
        code = f'''# Auto-generated Agent Script: {prompt}
import asyncio

async def run_task():
    print("Initializing task execution...")
    # Executing: {prompt}
    await asyncio.sleep(0.5)
    print("Task successfully completed.")

if __name__ == "__main__":
    asyncio.run(run_task())
'''

    try:
        ast.parse(code)
        validation_status = "✅ Python Syntax Validated: Pass (0 Syntax Errors)"
    except SyntaxError as e:
        validation_status = f"❌ Syntax Error Detected: {e}"

    return code, validation_status


# --- MODULE 4: Eduvision-DesignBot ---
def run_designbot(component_name, theme, format_type):
    if not component_name or not component_name.strip():
        component_name = "Dashboard Card Component"

    if format_type == "Tailwind CSS":
        output_code = f'''<div class="max-w-md mx-auto bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl text-white">
  <div class="flex items-center justify-between mb-4">
    <h3 class="text-xl font-bold tracking-tight text-indigo-400">{component_name}</h3>
    <span class="bg-indigo-500/10 text-indigo-400 text-xs px-2.5 py-1 rounded-full border border-indigo-500/20">{theme}</span>
  </div>
  <p class="text-slate-400 text-sm mb-6 leading-relaxed">
    Enterprise interface module built with responsive containers and optimized color scheme.
  </p>
  <button class="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-medium py-2.5 rounded-xl transition-all shadow-lg">
    Execute Action
  </button>
</div>'''
    else:
        output_code = f'''import React from 'react';

export const {re.sub(r'[^a-zA-Z0-9]', '', component_name.title())} = ({{ title = "{component_name}" }}) => {{
  return (
    <div style={{{{ padding: '24px', background: '{ "#0f172a" if "Dark" in theme else "#ffffff" }', borderRadius: '16px', border: '1px solid #334155', color: '{ "#fff" if "Dark" in theme else "#0f172a" }' }}}}>
      <h2 style={{{{ fontSize: '1.25rem', fontWeight: 'bold' }}}}>{{title}}</h2>
      <p style={{{{ opacity: 0.8, fontSize: '0.875rem', margin: '12px 0' }}}}>Theme context applied: {theme}</p>
      <button style={{{{ padding: '10px 20px', borderRadius: '8px', background: '#6366f1', color: '#fff', border: 'none', cursor: 'pointer' }}}}>
        Submit
      </button>
    </div>
  );
}};'''

    markdown_preview = f"""### 🎨 UI Specification Summary
- **Component Target:** `{component_name}`
- **Theme Styling:** `{theme}`
- **Output Standard:** `{format_type}`
"""
    return markdown_preview, output_code


# --- MODULE 5: Anant - Bengali Literature & Scripture Cantor RAG ---
def transcribe_audio(audio_filepath: str):
    if not audio_filepath:
        return ""
    result = whisper_model.transcribe(audio_filepath)
    return result.get("text", "").strip()

def preprocess_anant_query(user_input: str):
    clean_input = user_input.strip()
    is_native_script = any(ord(char) > 127 for char in clean_input)

    if is_native_script:
        return clean_input, "bn", "Bengali Script Input"

    banglish_keywords = ["kivabe", "kene", "kothay", "kon", "keh", "ke", "juddho", "amar", "jonno", "ki"]
    words = clean_input.lower().split()
    is_phonetic_bengali = any(w in banglish_keywords for w in words)

    m2m_tokenizer.src_lang = "en"
    encoded_input = m2m_tokenizer(clean_input, return_tensors="pt").to(device)

    with torch.inference_mode():
        generated_tokens = m2m_model.generate(
            **encoded_input,
            forced_bos_token_id=m2m_tokenizer.get_lang_id("bn")
        )
    bengali_search_query = m2m_tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)[0]

    if is_phonetic_bengali:
        return bengali_search_query, "bn", f"Phonetic Bengali -> {bengali_search_query}"
    else:
        return bengali_search_query, "en", f"English Input -> Translated Search: {bengali_search_query}"

def chat_with_anant(message, history):
    if history is None:
        history = []

    query = ""
    audio_file = None
    if isinstance(message, dict):
        query = message.get("text", "")
        files = message.get("files", [])
        if files:
            audio_file = files[0]
    else:
        query = message

    if audio_file:
        transcribed = transcribe_audio(audio_file)
        if transcribed:
            query = transcribed

    if not query or not query.strip():
        yield history + [{"role": "assistant", "content": "Please type a question or speak into the microphone."}]
        return

    history.append({"role": "user", "content": query})
    yield history

    bengali_query, output_language, status_msg = preprocess_anant_query(query)
    query_vector = embedder.encode([bengali_query], convert_to_numpy=True)
    distances, indices = anant_index.search(query_vector, k=1)
    retrieved_text = heritage_corpus[indices[0][0]]

    if output_language == "en":
        lang_instruction = "Respond in clear English based strictly on retrieved classical Bengali context."
    else:
        lang_instruction = "Respond in authentic Sadhu Bhasha (classical Bengali prose)."

    system_persona = (
        "You are Anant-the Cantor, an expert AI on classical Bengali literature, Sadhu Bhasha, and ancient scriptures.\n"
        f"{lang_instruction}\n"
        f"[Retrieved Context]: {retrieved_text}"
    )

    full_prompt = (
        f"<|im_start|>system\n{system_persona}<|im_end|>\n"
        f"<|im_start|>user\n{query}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )

    inputs = tokenizer(full_prompt, return_tensors="pt").to(device)

    with torch.inference_mode():
        generated_ids = model.generate(
            **inputs,
            max_new_tokens=250,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id
        )

    response_ids = generated_ids[0][inputs.input_ids.shape[-1]:]
    response_text = tokenizer.decode(response_ids, skip_special_tokens=True).strip()

    generated_img_markdown = ""
    if sd_pipeline:
        try:
            sd_prompt = f"Oil painting depicting Indian mythology and heritage scene, high detail, context: {retrieved_text[:60]}"
            with torch.inference_mode():
                img = sd_pipeline(sd_prompt, num_inference_steps=20, guidance_scale=7.5).images[0]
                img_path = "heritage_art.png"
                img.save(img_path)
                generated_img_markdown = f"\n\n---\n### 🎨 Generated Visual Artwork\n![Heritage Art]({img_path})\n"
        except Exception as e:
            print(f"Image generation skipped: {e}")

    formatted_response = (
        f"{response_text}\n\n"
        f"----\n"
        f"**📜 Ground Context:** *{retrieved_text}*"
        f"{generated_img_markdown}"
    )

    history.append({"role": "assistant", "content": formatted_response})
    yield history


# =====================================================================
# 4. GRADIO MULTI-TAB INTERFACE
# =====================================================================
with gr.Blocks(title="Eduvision AI Suite & Anant Cantor") as demo:
    gr.Markdown("# 🚀 Eduvision AI Suite")
    gr.Markdown("Enterprise AI Platform & Multimodal Feature Toolkit")

    with gr.Tabs():
        # --- TAB 1: Secure Check-In ---
        with gr.Tab("Secure Check-In"):
            gr.Markdown("### 🛡️ User Verification & Attendance Analytics")
            stats_box = gr.Markdown(value=get_checkin_stats())
            with gr.Row():
                with gr.Column():
                    name_input = gr.Textbox(label="User / Student Name", placeholder="Enter full name...")
                    role_input = gr.Dropdown(choices=["Student", "Faculty", "Admin", "Guest"], label="Role", value="Student")
                    with gr.Row():
                        checkin_btn = gr.Button("Submit Check-In", variant="primary")
                        clear_btn = gr.Button("Reset Logs", variant="stop")
                    checkin_output = gr.Textbox(label="Status Output", interactive=False)
                with gr.Column():
                    gr.Markdown("#### Real-time Attendance Logs")
                    checkin_table = gr.Dataframe(headers=["ID", "Name", "Role", "Timestamp"], value=get_recent_checkins(), interactive=False)
            
            checkin_btn.click(process_checkin, inputs=[name_input, role_input], outputs=[checkin_output, checkin_table, stats_box])
            clear_btn.click(clear_checkins, outputs=[checkin_output, checkin_table, stats_box])

        # --- TAB 2: Eduvision-RAGBot ---
        with gr.Tab("Eduvision-RAGBot"):
            gr.Markdown("### 📚 Vector Search Knowledge Assistant")
            with gr.Row():
                with gr.Column():
                    rag_input = gr.Textbox(label="Query / Search Topic", placeholder="Search architecture, RAG, DevBot, or check-in...")
                    custom_doc_input = gr.Textbox(label="Add Custom Knowledge Document (Optional)", placeholder="Paste custom knowledge text here...", lines=3)
                    rag_btn = gr.Button("Run Knowledge Assistant", variant="primary")
                with gr.Column():
                    rag_output = gr.Markdown(label="RAG Engine Response")
            
            rag_btn.click(run_ragbot, inputs=[rag_input, custom_doc_input], outputs=rag_output)

        # --- TAB 3: Eduvision-DevBot ---
        with gr.Tab("Eduvision-DevBot"):
            gr.Markdown("### 💻 Autonomous Code Generator & AST Validator")
            with gr.Row():
                with gr.Column():
                    dev_input = gr.Textbox(label="Module Description / Task", placeholder="e.g., User Authentication System", lines=2)
                    task_type = gr.Radio(choices=["FastAPI Endpoint", "SQLite CRUD", "Agent Workflow"], label="Architecture Template", value="FastAPI Endpoint")
                    dev_btn = gr.Button("Generate & Validate Code", variant="primary")
                    val_output = gr.Textbox(label="AST Syntax Check Result", interactive=False)
                with gr.Column():
                    dev_output = gr.Code(label="Generated Python Module", language="python")
            
            dev_btn.click(run_devbot, inputs=[dev_input, task_type], outputs=[dev_output, val_output])

        # --- TAB 4: Eduvision-DesignBot ---
        with gr.Tab("Eduvision-DesignBot"):
            gr.Markdown("### 🎨 UI Component & Blueprint Generator")
            with gr.Row():
                with gr.Column():
                    design_input = gr.Textbox(label="Component Name", placeholder="e.g. Analytics Executive Card")
                    theme_select = gr.Dropdown(choices=["Dark Mode Executive", "Clean Light Corporate", "Cyberpunk Modern"], label="Design Theme", value="Dark Mode Executive")
                    format_select = gr.Radio(choices=["Tailwind CSS", "React Component"], label="Export Format", value="Tailwind CSS")
                    design_btn = gr.Button("Generate UI Specification", variant="primary")
                with gr.Column():
                    design_preview = gr.Markdown()
                    design_code = gr.Code(label="Exported UI Code", language="html")
            
            design_btn.click(run_designbot, inputs=[design_input, theme_select, format_select], outputs=[design_preview, design_code])

        # --- TAB 5: Anant - Bengali Literature & Scripture Cantor ---
        with gr.Tab("Anant Cantor AI"):
            gr.Markdown("### 🌌 Anant-the Cantor: Bengali Literature & Scriptures Workspace")
            gr.Markdown("Featuring multilingual preprocessor (M2M100), Whisper voice transcription, LaBSE vector search, Qwen LLM, and Stable Diffusion heritage art.")

            anant_chatbot = gr.Chatbot(
                label="Conversation",
                height=520
            )

            anant_input = gr.MultimodalTextbox(
                interactive=True,
                placeholder="Ask about classical Bengali literature, scriptures, or education (Type or use mic)...",
                show_label=False,
                container=False
            )

            anant_input.submit(
                fn=chat_with_anant,
                inputs=[anant_input, anant_chatbot],
                outputs=[anant_chatbot]
            )

# =====================================================================
# 5. FASTAPI MOUNT & RENDER BINDING
# =====================================================================
app = FastAPI(title="Eduvision AI Suite & Anant Cantor API")

@app.get("/health")
def health_check():
    return {"status": "online", "suite": "Eduvision AI Suite & Anant Cantor"}

app = gr.mount_gradio_app(app, demo, path="/")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 7860))
    print(f"Launching Eduvision AI Suite on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)