import os
import sqlite3
from fastapi import FastAPI
import gradio as gr

# =====================================================================
# 1. DATABASE INITIALIZATION
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

# =====================================================================
# 2. SERVICE HANDLERS & LOGIC
# =====================================================================
def process_checkin(name, role):
    if not name or not name.strip():
        return "⚠️ Please provide a valid name.", get_recent_checkins()
    cursor.execute("INSERT INTO checkins (name, role) VALUES (?, ?)", (name, role))
    conn.commit()
    return f"✅ Secure Check-In successful for {name} ({role})!", get_recent_checkins()

def get_recent_checkins():
    cursor.execute("SELECT id, name, role, timestamp FROM checkins ORDER BY timestamp DESC LIMIT 10")
    rows = cursor.fetchall()
    return rows if rows else []

def run_ragbot(query, top_k=3):
    if not query or not query.strip():
        return "Please enter a valid query."
    
    knowledge_base = {
        "curriculum": "Eduvision AI Suite integrates core modules for automated learning paths, adaptive assessments, and real-time student analytics.",
        "architecture": "Built with a FastAPI asynchronous backend, a SQLite persistent store, and a modular Gradio executive interface.",
        "deployment": "Hosted on Render.com utilizing Python Uvicorn workers and dynamic port binding."
    }
    
    results = []
    for k, text in knowledge_base.items():
        if any(word in query.lower() for word in k.split()):
            results.append(f"📌 [Match: {k.upper()}] {text}")
            
    if not results:
        return f"🤖 [Eduvision-RAGBot] Synthesized response for '{query}': Based on general institutional knowledge, this query references standard operational parameters within the Eduvision framework."
    
    return "\n\n".join(results)

def run_devbot(prompt, task_type):
    if not prompt or not prompt.strip():
        return "# Please enter a coding prompt."
    
    if task_type == "FastAPI Endpoint":
        return f'''# Auto-generated FastAPI Endpoint by Eduvision-DevBot
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="{prompt}")

class Payload(BaseModel):
    data: str

@app.post("/api/v1/process")
def process_data(payload: Payload):
    return {{"status": "success", "received": payload.data, "module": "{prompt}"}}
'''
    elif task_type == "SQLite CRUD":
        return f'''# Auto-generated Database Handler by Eduvision-DevBot
import sqlite3

conn = sqlite3.connect("enterprise.db")
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, event TEXT)")
conn.commit()
'''
    else:
        return f'''# Auto-generated Agent Script for: {prompt}
import asyncio

async def run_agent_workflow():
    print("Initializing stateful planning and execution loop...")
    # Execution logic here
    
if __name__ == "__main__":
    asyncio.run(run_agent_workflow())
'''

def run_designbot(component_name, theme):
    if not component_name or not component_name.strip():
        component_name = "Executive Card Component"
        
    return f"""### 🎨 UI/UX Blueprint: {component_name} ({theme} Theme)

* **Layout Container:** Flexbox / Grid container with modern padding (`p-6`) and rounded borders (`rounded-xl`).
* **Color Palette:** Primary accents styled for high-contrast enterprise accessibility.
* **Tailwind CSS Snippet:**
```html
<div class="bg-slate-900 text-white p-6 rounded-xl shadow-2xl border border-slate-800">
  <h2 class="text-xl font-bold mb-3">{component_name}</h2>
  <p class="text-slate-400 text-sm mb-4">Optimized executive display node.</p>
  <button class="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg font-medium transition-all">
    Execute Module
  </button>
</div>
