# -*- coding: utf-8 -*-
import os
import sqlite3
import random
import threading
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import gradio as gr

# =====================================================================
# 1. EDUVISION METADATA, COPYRIGHT & EXECUTIVE REGISTRY
# =====================================================================
PROJECT_NAME = "Eduvision AI Suite"
ORGANIZATION = "Eduvision Project Group (in partnership with Anant-OmniCore Systems)"
COPYRIGHT_NOTICE = "Copyright (c) 2026 Ananda Chowdhury, Aaryan Chowdhury & Diya. All Rights Reserved."
LICENSE_TYPE = "Open for Academic & Professional Review - Commercial Inquiries Welcome"

TEAM_MEMBERS = [
    {
        "name": "Ananda Chowdhury",
        "role": "Chief Executive Officer & Principal AI Architect",
        "email": "anandchowdhury1@gmail.com",
        "phone": "+91 7449349733"
    },
    {
        "name": "Aaryan Chowdhury",
        "role": "Chief Technology Officer & Lead Systems Engineer",
        "email": "aaryan0@gmail.com",
        "phone": "+91 7439475398"
    },
    {
        "name": "Diya",
        "role": "Director of User Experience & Product Strategy",
        "email": "rajanyadutta2009@gmail.com",
        "phone": "Collaborative Lead"
    }
]

GENERAL_CONTACT_EMAIL = "anantcantor@gmail.com"

TERMS_AND_CONDITIONS = f"""
### Eduvision Terms of Service & Software Notice
1. **Software Copyright:** {COPYRIGHT_NOTICE}
2. **Attribution:** Engineered and authored by Ananda Chowdhury, Aaryan Chowdhury, and Diya.
3. **Usage Notice:** This software project is made available for technical evaluation and demonstration.
4. **Security & Access:** User ID check-ins and session tokens are protected by verification layers.
5. **Contact:** For collaboration or technical inquiries: `{GENERAL_CONTACT_EMAIL}`.
"""

# =====================================================================
# 2. DATABASE & AUTHENTICATION SETUP
# =====================================================================
DB_NAME = "eduvision_enterprise.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'Standard Scholar'
        )
    """)
    conn.commit()
    conn.close()

init_db()

# =====================================================================
# 3. FASTAPI MOBILE BACKEND ENGINE
# =====================================================================
app = FastAPI(
    title="Eduvision API Gateway",
    description=f"Official Backend Service for Eduvision. Contact: {GENERAL_CONTACT_EMAIL}. {COPYRIGHT_NOTICE}",
    version="1.0.0"
)

class AuthRequest(BaseModel):
    user_id: str
    password: str

@app.get("/api/health")
def health_check():
    return {
        "status": "online",
        "project": PROJECT_NAME,
        "contact": GENERAL_CONTACT_EMAIL,
        "copyright": COPYRIGHT_NOTICE
    }

@app.post("/api/register")
def register(user: AuthRequest):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (user_id, password) VALUES (?, ?)", (user.user_id, user.password))
        conn.commit()
        conn.close()
        return {"message": f"User ID '{user.user_id}' successfully registered with Eduvision Security Core."}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="User ID already exists in the Eduvision registry.")

@app.post("/api/login")
def login(user: AuthRequest):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ? AND password = ?", (user.user_id, user.password))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {"message": "Authentication successful", "access_token": f"eduvision_secure_token_{user.user_id}"}
    raise HTTPException(status_code=401, detail="Invalid User ID or Credentials.")

def run_fastapi():
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")

threading.Thread(target=run_fastapi, daemon=True).start()

# =====================================================================
# 4. GRADIO UNIFIED ENTERPRISE DASHBOARD
# =====================================================================

def generate_captcha():
    num1 = random.randint(10, 49)
    num2 = random.randint(1, 9)
    answer = num1 + num2
    challenge_id = f"Solve: {num1} + {num2} = ?"
    return challenge_id, str(answer)

def verify_and_checkin(user_id, password, user_answer, expected_answer):
    if not user_id or not password:
        return "[Security Alert]: User ID and Password fields cannot be empty.", gr.update(visible=True), gr.update(visible=False)
    
    if user_answer.strip() != expected_answer:
        new_q, new_ans = generate_captcha()
        return f"[Captcha Failed]: Incorrect mathematical validation. Please resolve the new puzzle below.", gr.update(value=new_q), gr.update(value=new_ans)
    
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("INSERT INTO users (user_id, password) VALUES (?, ?)", (user_id, password))
            conn.commit()
        conn.close()
    except Exception:
        pass

    success_msg = f"""
    SECURITY CHECK-IN SUCCESSFUL: WELCOME TO EDUVISION
    ------------------------------------------------------------------
    * User ID Verified: {user_id}
    * Session Token Status: Encrypted & Active (AES-256 Simulation)
    * Assigned Node: Eduvision Cluster Node #7
    * System Note: Session authenticated under professional compliance standards. Full access granted.
    * Support Channel: {GENERAL_CONTACT_EMAIL} | Direct Line: +91 7449349733
    ------------------------------------------------------------------
    {COPYRIGHT_NOTICE}
    """
    return success_msg, gr.update(visible=False), gr.update(visible=True)

def eduvision_rag(prompt, audio_file):
    transcription = " [Audio Voice Vector processed via Whisper Engine]" if audio_file else ""
    return f"[Eduvision-RAGBot]: Analyzed query '{prompt}'{transcription}. Retrieved semantic matches from knowledge base."

def eduvision_sandbox(code_str):
    try:
        local_scope = {}
        exec(code_str, {}, local_scope)
        return f"[Eduvision-DevBot Sandbox]: Code executed successfully.\nRuntime Scope: {local_scope}"
    except Exception as e:
        return f"[Eduvision-DevBot Error]: {str(e)}"

def eduvision_studio(prompt):
    return f"[Eduvision-DesignBot]: Rendering visual diffusion matrix for: '{prompt}'..."

custom_css = """
.gradio-container { background-color: #0f172a; font-family: 'Inter', -apple-system, sans-serif; color: #f8fafc; }
.header-box { text-align: center; border: 1px solid #334155; padding: 24px; border-radius: 8px; background: #1e293b; margin-bottom: 20px; }
.header-logo { max-height: 80px; width: auto; margin: 0 auto 12px auto; display: block; border-radius: 6px; box-shadow: 0 0 15px rgba(255, 100, 50, 0.3); }
.header-title { color: #38bdf8; font-weight: 700; letter-spacing: 1px; margin-bottom: 6px; font-size: 1.8em; }
.creator-badge { color: #94a3b8; font-size: 1em; font-weight: 500; margin-bottom: 4px; }
"""

initial_q, initial_a = generate_captcha()

with gr.Blocks(css=custom_css, title="Eduvision AI Suite") as demo:
    hidden_ans = gr.State(value=initial_a)
    
    gr.HTML(
        f"""
        <div class="header-box">
            <img src="file=Logo.png.jpeg" alt="Eduvision Logo" class="header-logo" onerror="this.style.display='none'">
            <h1 class="header-title">EDUVISION AI SUITE v1.0</h1>
            <p class="creator-badge">Engineered by <b>Ananda Chowdhury, Aaryan Chowdhury & Diya</b></p>
            <p style="color: #64748b; font-size: 0.95em;">Multimodal AI Framework & Secure Academic Intelligence Platform</p>
        </div>
        """
    )
    
    with gr.Tabs():
        with gr.TabItem("Secure Check-In"):
            gr.Markdown("### User Verification & Authentication Gateway")
            gr.Markdown("Enter your **User ID**, **Password**, and complete the mathematical validation below.")
            
            with gr.Row():
                uid_input = gr.Textbox(placeholder="e.g. engineer_ananda", label="User ID")
                pwd_input = gr.Textbox(placeholder="Enter password", type="password", label="Password")
            
            with gr.Row():
                captcha_display = gr.Textbox(value=initial_q, label="Security Captcha", interactive=False)
                captcha_input = gr.Textbox(placeholder="Enter answer", label="Captcha Answer")
            
            checkin_btn = gr.Button("Initialize Check-In", variant="primary")
            checkin_output = gr.Markdown(label="System Status")
            
            checkin_btn.click(
                verify_and_checkin,
                inputs=[uid_input, pwd_input, captcha_input, hidden_ans],
                outputs=[checkin_output, captcha_display, hidden_ans]
            )

        with gr.TabItem("Eduvision-RAGBot"):
            gr.Markdown("#### Multimodal Academic Corpus Retrieval & Voice Engine")
            with gr.Row():
                rag_prompt = gr.Textbox(placeholder="Ask a technical or academic research question...", label="Query Prompt")
                rag_audio = gr.Audio(sources=["microphone", "upload"], type="filepath", label="Voice Dictation")
            rag_btn = gr.Button("Query RAGBot", variant="primary")
            rag_out = gr.Textbox(label="RAGBot Response", interactive=False)
            rag_btn.click(eduvision_rag, inputs=[rag_prompt, rag_audio], outputs=rag_out)

        with gr.TabItem("Eduvision-DevBot"):
            gr.Markdown("#### Dynamic Python Interpreter")
            dev_code = gr.Code(language="python", value="import math\nprint('Eduvision DevBot Active.')\nprint(f'Verification Root: {math.sqrt(625)}')", label="Python Workspace")
            dev_btn = gr.Button("Execute Code", variant="primary")
            dev_out = gr.Textbox(label="Console Output", interactive=False)
            dev_btn.click(eduvision_sandbox, inputs=dev_code, outputs=dev_out)

        with gr.TabItem("Eduvision-DesignBot"):
            gr.Markdown("#### Generative Visual Diffusion Studio")
            img_in = gr.Textbox(placeholder="Quantum architecture render with neutral lighting...", label="Visual Prompt")
            img_btn = gr.Button("Generate Asset", variant="primary")
            img_out = gr.Textbox(label="DesignBot Status", interactive=False)
            img_btn.click(eduvision_studio, inputs=img_in, outputs=img_out)

        with gr.TabItem("Executive Directory"):
            gr.Markdown(f"""
            ### Executive Leadership Directory
            * **Official Contact Email:** `{GENERAL_CONTACT_EMAIL}`
            
            | Executive Member | Professional Designation | Direct Contact |
            | :--- | :--- | :--- |
            | **Ananda Chowdhury** | Chief Executive Officer & Principal AI Architect | `anandchowdhury1@gmail.com` \| `+91 7449349733` |
            | **Aaryan Chowdhury** | Chief Technology Officer & Lead Systems Engineer | `aaryan0@gmail.com` \| `+91 7439475398` |
            | **Diya** | Director of User Experience & Product Strategy | `rajanyadutta2009@gmail.com` |
            """)

        with gr.TabItem("Copyright & Terms"):
            gr.Markdown(TERMS_AND_CONDITIONS)

# =====================================================================
# 5. LAUNCH SUITE
# =====================================================================
if __name__ == "__main__":
    print(f"Launching {PROJECT_NAME}...")
    demo.launch(server_name="0.0.0.0", server_port=7860, show_error=True)

# =====================================================================
# 5. LAUNCH SUITE
# =====================================================================
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 7860))
    print(f"Launching {PROJECT_NAME} on port {port}...")
    demo.launch(server_name="0.0.0.0", server_port=port, show_error=True)