import os
import sys
import json
import sqlite3
import itertools
import time
import random
import re
import uuid
import base64
import asyncio

from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv


from src.biomechanics import search_biomechanics
from src.graph import app as langgraph_app 
from src.importer import compact_logs_to_profile
from langgraph.types import Command
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_ollama import ChatOllama

# INITIALIZATION

APP_SESSION_TOKEN = str(uuid.uuid4())[:8]
os.environ["ACTIVE_USER_ID"] = "guest_user"
load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
DB_PATH = os.getenv("DB_PATH", "checkpoints.sqlite")

API_KEYS_POOL = [
    os.getenv("GOOGLE_API_KEY"),
    os.getenv("GOOGLE_API_KEY_BACKUP") 
]

class CloudKeyRotator:
    def __init__(self, keys):
        self.clean_keys = [k for k in keys if k and k.strip() != ""]
        if not self.clean_keys:
            self.clean_keys = ["MISSING_KEY"]
        random.shuffle(self.clean_keys)
        self.pool = itertools.cycle(self.clean_keys)
        self.current_key = next(self.pool)
        os.environ["GOOGLE_API_KEY"] = self.current_key
        print(f"🔑 [System Key Rotator] Initialized and balanced API Key pool.")

    def rotate(self):
        self.current_key = next(self.pool)
        os.environ["GOOGLE_API_KEY"] = self.current_key
        print(f"🔄 [System Key Rotator] 429 Limit Hit! Swapped environment to backup API Key.")

key_rotator = CloudKeyRotator(API_KEYS_POOL)

def init_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS athlete_profile (
            id TEXT PRIMARY KEY, name TEXT, athlete_type TEXT, experience_level TEXT, 
            injury_flags TEXT, summary TEXT, username TEXT, password TEXT, avatar_color TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS training_routines (
            routine_id TEXT PRIMARY KEY, athlete_id TEXT, day_of_week TEXT, focus_area TEXT, workout_data TEXT
        )
    """)
    columns_to_add = [
        ("username", "TEXT DEFAULT ''"),
        ("password", "TEXT DEFAULT ''"),
        ("avatar_color", "TEXT DEFAULT '#FF3278'")
    ]
    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE athlete_profile ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            pass 
    conn.commit()
    conn.close()

init_database()


# FASTAPI SERVER SETUP

app = FastAPI(title="FlexRoute Brain")

# This allows html file to securely talk to this Python server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# PYDANTIC DATA MODELS (For Receiving Data from js)

class ChatRequest(BaseModel):
    user_input: str

class ProfileRegistration(BaseModel):
    user_id: str
    name: str
    training_style: str
    username: str
    password: str
    avatar_color: str

class LoginRequest(BaseModel):
    user_id: str

class ProfileCalibration(BaseModel):
    experience_level: str

class RoutineCommit(BaseModel):
    proposed_json_str: str

# Model for Editing Profiles
class ProfileUpdate(BaseModel):
    name: str
    training_style: str
    experience_level: str
    avatar_color: str

import shutil

# DATABASE & PROFILE ENDPOINTS 

@app.post("/api/abort")
def abort_process():
    with open("abort_signal.tmp", "w") as f:
        f.write("ABORT")
    return {"status": "Kill signal deployed."}

@app.get("/api/profiles")
def fetch_all_profiles():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, username, password, avatar_color FROM athlete_profile")
        rows = cursor.fetchall()
        conn.close()
        
        profiles = [{"id": r[0], "name": r[1], "username": r[2], "password": r[3], "avatar_color": r[4] if r[4] else "#FF3278"} for r in rows]
        return profiles
    except Exception as e:
        print(f"Error fetching gateway profiles: {e}")
        return []

@app.post("/api/profile/register")
def register_new_profile(data: ProfileRegistration):
    try:
        os.environ["ACTIVE_USER_ID"] = data.user_id
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO athlete_profile (id, name, athlete_type, experience_level, injury_flags, summary, username, password, avatar_color)
            VALUES (?, ?, ?, 'Unset', '["None"]', 'Initialized.', ?, ?, ?)
        """, (data.user_id, data.name, data.training_style if data.training_style else "General", data.username, data.password, data.avatar_color))
        conn.commit()
        conn.close()
        print(f"[Database] Saved permanent user rows: {data.name}")
        return {"status": "success"}
    except Exception as e:
        print(f"Failed to append profile database sequence: {e}")
        return {"error": str(e)}

@app.get("/api/profile/{user_id}/auth")
def request_profile_login(user_id: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name, password FROM athlete_profile WHERE id=?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"user_id": user_id, "name": row[0], "password": row[1]}
        return {"error": "Not found"}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/profile/login")
def confirm_authenticated_login(data: LoginRequest):
    os.environ["ACTIVE_USER_ID"] = data.user_id
    return {"status": "success"}

@app.get("/api/profile/current")
def fetch_current_profile():
    active_id = os.environ.get("ACTIVE_USER_ID", "guest_user")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name, athlete_type, experience_level, injury_flags FROM athlete_profile WHERE id=?", (active_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            name, athlete_type, experience_level, flags_raw = row
            return {
                "name": name,
                "athlete_type": athlete_type or "Unset",
                "estimated_experience_level": experience_level or "Unset",
                "injury_or_fatigue_flags": json.loads(flags_raw) if flags_raw else ["None"]
            }
        else:
            return {"name": active_id.title(), "athlete_type": "Unset", "estimated_experience_level": "Unset", "injury_or_fatigue_flags": ["None"]}
    except Exception as e:
        print(f"Error extracting identity packet variables: {e}")
        return {"error": str(e)}

@app.post("/api/profile/calibrate")
def calibrate_profile(data: ProfileCalibration):
    active_id = os.environ.get("ACTIVE_USER_ID", "guest_user")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE athlete_profile SET experience_level=? WHERE id=?", (data.experience_level, active_id))
        conn.commit()
        conn.close()
        print(f"✅ [Database] Calibrated experience level to {data.experience_level} for {active_id}")
        return {"status": "success"}
    except Exception as e:
        print(f"❌ [Database] Calibration failed: {e}")
        return {"error": str(e)}

@app.put("/api/profile/edit")
def edit_active_profile(data: ProfileUpdate):
    active_id = os.environ.get("ACTIVE_USER_ID", "guest_user")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE athlete_profile 
            SET name=?, athlete_type=?, experience_level=?, avatar_color=? 
            WHERE id=?
        """, (data.name, data.training_style, data.experience_level, data.avatar_color, active_id))
        conn.commit()
        conn.close()
        print(f"✅ [Database] Profile updated successfully for: {active_id}")
        return {"status": "success"}
    except Exception as e:
        print(f"❌ [Database] Profile update failed: {e}")
        return {"error": str(e)}

@app.delete("/api/profile/{user_id}")
def delete_athlete_profile(user_id: str):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM athlete_profile WHERE id=?", (user_id,))
        conn.commit()
        conn.close()
        print(f"[Database] Dropped account row: {user_id}")
        return {"status": "success"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/routine")
def load_active_routine():
    active_id = os.environ.get("ACTIVE_USER_ID")
    if not active_id or active_id == "guest_user":
        return []

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT day_of_week, focus_area, workout_data FROM training_routines WHERE athlete_id=?", (active_id,))
        rows = cursor.fetchall()
        conn.close()

        routines = []
        day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        row_map = {row[0]: {"focus_area": row[1], "exercises": json.loads(row[2])} for row in rows}
        
        for day in day_order:
            if day in row_map:
                routines.append({"day_of_week": day, "focus_area": row_map[day]["focus_area"], "exercises": row_map[day]["exercises"]})
            else:
                routines.append({"day_of_week": day, "focus_area": "Rest Day", "exercises": []})

        return routines
    except Exception as e:
        print(f"❌ Error loading active routine block: {e}")
        return []

@app.post("/api/routine")
def commit_proposed_routine(data: RoutineCommit):
    active_id = os.environ.get("ACTIVE_USER_ID")
    if not active_id or active_id == "guest_user": 
        return {"error": "No active user"}

    try:
        days_list = json.loads(data.proposed_json_str)       
        conn = sqlite3.connect(DB_PATH, timeout=15.0)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM training_routines WHERE athlete_id=?", (active_id,))
        
        for day_data in days_list:
            day = day_data.get("day_of_week", day_data.get("day", "Unknown"))
            focus = day_data.get("focus_area", "Rest Day")
            exercises = day_data.get("exercises", [])
            
            workout_json = json.dumps(exercises)
            routine_unique_id = f"{active_id}_{day}"
            
            cursor.execute("""
            INSERT INTO training_routines (routine_id, athlete_id, day_of_week, focus_area, workout_data)
                    VALUES (?, ?, ?, ?, ?)
            """, (routine_unique_id, active_id, day, focus, workout_json))
            
        conn.commit()
        conn.close()
        print(f"✅ SQLite Synced: Macrocycle committed for user: {active_id}")
        return {"status": "success"}
    except Exception as e:
        print(f"❌ Transaction Fault syncing macrocycle elements: {e}")
        return {"error": str(e)}

@app.delete("/api/routine")
def clear_active_routine():
    active_id = os.environ.get("ACTIVE_USER_ID")
    if not active_id or active_id == "guest_user":
        return {"error": "No active user"}
    try:
        conn = sqlite3.connect(DB_PATH, timeout=15.0)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM training_routines WHERE athlete_id=?", (active_id,))
        conn.commit()
        conn.close()
        print(f"🗑️ [Database] Wiped active routine for user: {active_id}")
        return {"status": "success"}
    except Exception as e:
        return {"error": str(e)}

# NATIVE FILE UPLOADER
@app.post("/api/upload")
def upload_workout_file(file: UploadFile = File(...)):
    # Save the file temporarily so importer.py can read it
    file_path = f"temp_{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    compact_logs_to_profile(file_path)
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        active_id = os.environ.get("ACTIVE_USER_ID", "guest_user")
        cursor.execute("SELECT name, athlete_type, experience_level, injury_flags, summary FROM athlete_profile WHERE id=?", (active_id,))
        row = cursor.fetchone()
        conn.close()

        # Clean up the temp file
        if os.path.exists(file_path):
            os.remove(file_path)

        if row:
            name, athlete_type, experience_level, flags_raw, summary = row
            return {
                "name": name,
                "athlete_type": athlete_type,
                "estimated_experience_level": experience_level,
                "injury_or_fatigue_flags": json.loads(flags_raw) if flags_raw else ["None"],
                "general_summary": summary if summary else ""
            }
        return {"error": "Profile lookup failed."}
    except Exception as e:
        return {"error": str(e)}

# AI ENGINE ENDPOINT

@app.post("/api/chat")
def process_chat_query(req: ChatRequest):  
    start_time = time.time()
    
    try:
        user_input = req.user_input
        print(f"\n▶️ [EngineWorker] Pipeline activated for input: '{user_input}'")
        clean_msg = user_input.strip().lower()
        active_id = os.environ.get("ACTIVE_USER_ID", "guest_user")

        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT name, athlete_type, injury_flags FROM athlete_profile WHERE id=?", (active_id,))
            db_user = cursor.fetchone()
            conn.close()
        except Exception as e:
            print(f"⚠️ [EngineWorker] Failed to fetch active user: {e}")
            db_user = None
        
        active_name = db_user[0] if db_user else active_id.title()
        active_type = db_user[1] if db_user else "General Training"
        active_injuries_raw = db_user[2] if db_user else '["None"]'
        try:
            parsed_injuries = json.loads(active_injuries_raw)
            active_injuries = ", ".join(parsed_injuries) if parsed_injuries else "None"
        except Exception:
            active_injuries = str(active_injuries_raw)

        def exact_match(keyword_list, text):
            pattern = r'\b(?:' + '|'.join(map(re.escape, keyword_list)) + r')\b'
            return bool(re.search(pattern, text))

        structural_keywords = ["split", "routine", "program", "plan", "workout", "macrocycle", "generate", "build", "create", "script"]
        medical_keywords = ["injured", "injury", "healed", "clear", "tear", "tore", "strain", "recovered", "tweaked", "sprain", "broken"]
        diet_keywords = ["diet", "food", "meal", "eat", "calories", "macros", "protein", "bulk", "cut", "nutrition"]
        question_keywords = ["why", "how", "what", "best", "opinion", "fix", "form", "cue"]
        casual_greetings = ["hello", "hi", "hey", "sup", "yo", "dude", "ok", "okay", "thanks", "thank you", "cool", "awesome", "alright", "got it"]
        
        intent = None
        
        if exact_match(medical_keywords, clean_msg):
            intent = "MEDICAL"
            print("⚡ [Pre-Router] Intercepted MEDICAL intent.")
        elif exact_match(diet_keywords, clean_msg):
            intent = "CHAT"
            print("⚡ [Pre-Router] Intercepted DIET/NUTRITION intent.")
        elif exact_match(structural_keywords, clean_msg):
            intent = "ROUTINE"
            print("⚡ [Pre-Router] Intercepted ROUTINE intent.")
        elif exact_match(question_keywords, clean_msg) or exact_match(casual_greetings, clean_msg):
            intent = "CHAT"
            print("⚡ [Pre-Router] Intercepted CHAT intent.")
            
        # Catch typos and short words instantly
        if not intent and len(clean_msg) <= 5:
            intent = "CHAT"
            print("⚡ [Pre-Router] Intercepted short message/typo. Defaulting to CHAT intent.")
            
        if not intent:
            print("🧠 [Semantic Router] Asking Mistral to classify intent...")
            try:
                router_prompt = f"""Analyze the user's message and classify the core intent into EXACTLY ONE of these three categories:
                1. ROUTINE: The user is explicitly COMMANDING you to build, generate, or create a workout plan/split.
                2. MEDICAL: The user is explicitly REPORTING a new physical injury, stating they are healed, or asking to "clear guard rails". DO NOT pick this if they are asking a question.
                3. CHAT: The user is asking a QUESTION for advice/opinions (e.g., "why does my back hurt?", "how do I fix my bench?"), discussing diet, or making casual conversation.

                User Message: "{clean_msg}"

                STRICT RULE: Respond with EXACTLY ONE WORD: ROUTINE, MEDICAL, or CHAT. If the message is a question about fitness concepts or pain, default to CHAT."""
                
                route_llm = ChatOllama(
                    model="mistral",
                    temperature=0.0,
                    num_predict=5,
                    base_url=OLLAMA_URL
                )
                intent = route_llm.invoke([HumanMessage(content=router_prompt)]).content.strip().upper()
                print(f"🚦 [Semantic Router] Mistral classified intent as: {intent}")
            except Exception as e:
                print(f"⚠️ [Semantic Router] Failed: {e}")
                intent = "CHAT"

        is_conversational = "CHAT" in intent
        is_structural = "ROUTINE" in intent
        is_medical = "MEDICAL" in intent

        structural_keywords = ["split", "routine", "program", "plan", "workout", "macrocycle", "schedule", "modify", "add", "week"]
        hitl_keywords = ["approve", "accept", "yes", "reject", "deny", "no"]

        is_hitl = exact_match(hitl_keywords, clean_msg)
        config = {"configurable": {"thread_id": f"thread_{active_id}_{APP_SESSION_TOKEN}"}}
        state = langgraph_app.get_state(config)
        
        if is_hitl and state and state.values and state.values.get("messages"):
            prev_msg = state.values["messages"][-1].content.lower()
            if any(kw in prev_msg for kw in structural_keywords):
                is_structural = True
                
        proposed_routine = state.values.get("proposed_routine") if state and state.values else None
        is_graph_interrupted = bool(state.next) if state else False

        if is_hitl and proposed_routine and not is_graph_interrupted:
            if clean_msg in ["approve", "accept", "yes"]:
                print("⚡ Structural Routine Authorized. Emitting sync signal...")
                sync_result = commit_proposed_routine(RoutineCommit(proposed_json_str=proposed_routine))
                
                if "error" in sync_result:
                    return {
                        "route_decision": "system",
                        "response": f"❌ Database locked or error occurred: {sync_result['error']}. Please try typing 'approve' again.",
                        "time_taken": round(time.time() - start_time, 2)
                    }

                # Clear state memory 
                langgraph_app.update_state(config, {"proposed_routine": None})
                
                return {
                    "route_decision": "local",
                    "response": "✅ Routine Approved and Saved! Check your Routine Builder tab.",
                    "time_taken": round(time.time() - start_time, 2)
                }
            else:
                print("🚫 User Denied Sync. Clearing proposed routine from memory.")
                langgraph_app.update_state(config, {"proposed_routine": None})
                return {
                    "route_decision": "local",
                    "response": "🚫 Routine discarded. Let me know how you want to tweak it!",
                    "time_taken": round(time.time() - start_time, 2)
                }
        
        if not is_structural and not is_medical and not is_hitl:
            print("🎯 [Local Fast-Pass] Casual chat detected. Routing directly to Llama to save quota.")
            retrieved_knowledge = ""
            
            # 1. Words that suggest a question or request is being made
            question_triggers = ["how", "why", "what", "best", "fix", "can", "give", "need"]
            
            # 2. Expanded to include Diet, Nutrition, and Bulking/Cutting
            fitness_triggers = ["form", "cue", "hurt", "pain", "knee", "back", "shoulder", "muscle", "technique", "squat", "bench", "deadlift", "exercise", "diet", "bulk", "bulking", "cut", "cutting", "nutrition", "food", "meal", "calories", "macros", "protein"]
            
            # 3. Phrases that are purely conversational
            small_talk_phrases = ["how are you", "how are u", "whats up", "what's up", "how's it going", "who are you", "what are you doing", "what are you"]
            
            is_small_talk = any(phrase in clean_msg for phrase in small_talk_phrases) or len(clean_msg) <= 5
            has_trigger_word = exact_match(question_triggers + fitness_triggers, clean_msg)
            
            # Only fire the RAG database if it has a trigger word and its not small talk
            if has_trigger_word and not is_small_talk:
                print("🔍 [RAG Engine] Advice/Diet question detected in Fast-Pass. Searching Local Qdrant...")
                try:
                    results = search_biomechanics(user_input, k=3)
                    if results:
                        retrieved_knowledge = "\n### CRITICAL KNOWLEDGE BASE:\n"
                        for res in results:
                            retrieved_knowledge += f"- {res.page_content}\n"
                except Exception as e:
                    print(f"⚠️ [RAG Engine] Qdrant search failed: {e}")
            
           # AI Role
            system_prompt = f"""You are FlexRoute, an intelligent AI fitness architect.
            Current Athlete: {active_name}
            Training Style: {active_type}
            Active Injuries: {active_injuries}
            
            {retrieved_knowledge}
            
            CRITICAL BEHAVIOR RULES:
            1. NORMAL CHAT: If the user says hi, hey, or asks how you are, reply naturally like a normal AI (e.g., "I'm doing great, {active_name}! How can I help you today?"). Keep small talk brief. 
            2. DO NOT FORCE CONTEXT: Do NOT forcefully bring up their injuries, training style, or give unsolicited advice during casual greetings. Only discuss their injury if they ask a fitness question.
            3. FITNESS/DIET: Answer fitness and nutrition questions directly and accurately.
            4. NO DISCLAIMERS: NEVER output medical or legal disclaimers (e.g., "I cannot diagnose", "Consult a doctor"). Answer confidently based on your biomechanics knowledge.
            5. NO ROUTINES: NEVER generate workout splits or JSON arrays in this mode."""
            
            state_messages = state.values.get("messages", []) if state and state.values else []
            compiled_msgs = [SystemMessage(content=system_prompt)] + list(state_messages[-4:]) + [HumanMessage(content=user_input)]
        
            try:
                # Increased num_predict to 1000 so it can finish long tables
                local_chat_llm = ChatOllama(model="mistral", temperature=0.7, num_predict=1000, base_url=OLLAMA_URL)
                response = local_chat_llm.invoke(compiled_msgs)
                langgraph_app.update_state(config, {"messages": [HumanMessage(content=user_input), AIMessage(content=response.content)]})
                
                return {
                    "route_decision": "local",
                    "response": response.content,
                    "time_taken": round(time.time() - start_time, 2)
                }
            except Exception as e:
                print(f"Local Fast-Pass failover triggered standard pipeline context: {e}")

        print("☁️ [EngineWorker] Routing to LangGraph Core Workflow Pipeline...")
        if clean_msg not in ["approve", "accept", "yes", "reject", "deny", "no"]:
            langgraph_app.update_state(config, {"proposed_routine": None})
            
        max_attempts = len(key_rotator.clean_keys) if key_rotator.clean_keys else 1
        for attempt in range(max_attempts):
            try:
                state = langgraph_app.get_state(config)
                
                if state.next:
                    if clean_msg in ["approve", "accept", "yes"]:
                        langgraph_app.update_state(config, {"messages": [HumanMessage(content=user_input)]})
                        result = langgraph_app.invoke(Command(resume="approve"), config=config)
                    elif clean_msg in ["reject", "deny", "no"]:
                        langgraph_app.update_state(config, {"messages": [HumanMessage(content=user_input)]})
                        result = langgraph_app.invoke(Command(resume="reject"), config=config)
                    else:
                        langgraph_app.invoke(Command(resume="reject"), config=config)
                        langgraph_app.update_state(config, {"proposed_routine": None})
                        result = langgraph_app.invoke({"messages": [HumanMessage(content=user_input)]}, config=config)
                else:
                    result = langgraph_app.invoke({"messages": [HumanMessage(content=user_input)]}, config=config)
                
                new_state = langgraph_app.get_state(config)
                
                if new_state.next:
                    ai_response = "### 🛑 AUTHORIZATION REQUIRED\nPlease confirm synchronization."
                    try:
                        if hasattr(new_state, 'tasks') and len(new_state.tasks) > 0:
                            interrupts = new_state.tasks[0].interrupts
                            if interrupts and len(interrupts) > 0:
                                ai_response = interrupts[0].value.get("message", ai_response)
                    except Exception as e:
                        print(f"Interrupt extraction warning: {e}")
                        
                    output_payload = {
                        "route_decision": "safety", 
                        "response": ai_response,
                        "require_approval": True 
                    }
                else:
                    messages = result.get("messages", [])
                    ai_response = messages[-1].content if len(messages) > 0 else "Action completed."
                    output_payload = {"route_decision": "graph", "response": ai_response}
                    if new_state.values.get("proposed_routine"):
                        output_payload["require_approval"] = True
                
                try:
                    conn = sqlite3.connect(DB_PATH, timeout=10.0)
                    cursor = conn.cursor()
                    cursor.execute("SELECT injury_flags FROM athlete_profile WHERE id=?", (active_id,))
                    updated_flags_row = cursor.fetchone()
                    conn.close()
                    if updated_flags_row:
                        output_payload["refresh_dashboard"] = True
                        output_payload["new_injury_flags"] = json.loads(updated_flags_row[0])
                except Exception as db_sync_err:
                    print(f"❌ [Sync Engine] UI sync fault skipped: {db_sync_err}")
                
                output_payload["time_taken"] = round(time.time() - start_time, 2)
                return output_payload
            
            except Exception as e:
                print(f"⚠️ [EngineWorker] LangGraph pipeline failed: {e}")
                if attempt == max_attempts - 1:
                    print(f"❌ [EngineWorker] All key rotation attempts exhausted. Triggering Smart Local Fallback...")
                    
                    try:
                        athlete_context = f"Athlete Profile: {active_name} | Style: {active_type} | Injuries: {active_injuries}"
                        local_survival_llm = ChatOllama(model="mistral", temperature=0.7, base_url=OLLAMA_URL)
                        state_messages = state.values.get("messages", []) if state and state.values else []
                        
                        if is_structural:
                            system_prompt = f"""You are the FlexRoute Coach running in offline structural adjustment mode.
                            Context: {athlete_context}
                            Task: Construct a complete, hyper-detailed 7-day training schedule.
                            CRITICAL STRUCTURAL RULES:
                            1. You MUST respond ONLY with a valid, cleanly formatted JSON array.
                            2. Every active day must have 3 to 4 exercises.
                            3. FORMATTING: 'sets' must be a single string integer (e.g., "3"). 'reps' must be a text range (e.g., "10-12 reps").
                            EXACT JSON ARRAY EXAMPLE TO REPLICATE:
                            [
                            {{
                                "day_of_week": "Monday",
                                "focus_area": "Lower Body",
                                "exercises": [
                                {{
                                    "name": "Squats",
                                    "sets": "3",
                                    "reps": "12 reps",
                                    "explanation": "Maintain core brace."
                                }}
                                ]
                            }}
                            ]"""
                            fallback_msg = [SystemMessage(content=system_prompt)] + list(state_messages) + [HumanMessage(content=user_input)]
                            
                            json_llm = ChatOllama(model="mistral", temperature=0.2, base_url=OLLAMA_URL)
                            response = json_llm.invoke(fallback_msg)
                            raw_text = response.content.strip()
                            raw_text = raw_text.replace("```json", "").replace("```", "").strip()
                            parsed_routine = json.loads(raw_text)
                            
                            normalized_routine = []
                            for day in parsed_routine:
                                day_name = day.get("day_of_week", day.get("day", "Unknown"))
                                focus = day.get("focus_area", "Rest Day")
                                raw_exercises = day.get("exercises", [])
                                clean_exercises = []
                                for ex in raw_exercises:
                                    if isinstance(ex, dict):
                                        clean_exercises.append({
                                            "name": ex.get("name", "Modified Movement"),
                                            "sets": str(ex.get("sets", "3")),
                                            "reps": str(ex.get("reps", "8-12 reps")),
                                            "explanation": ex.get("explanation", "Maintain strict form to protect joints.")
                                        })
                                normalized_routine.append({
                                    "day_of_week": day_name,
                                    "focus_area": focus,
                                    "exercises": clean_exercises
                                })

                            routine_json = json.dumps(normalized_routine)
                            langgraph_app.update_state(config, {"proposed_routine": routine_json})
                            
                            ai_response = f"⚠️ **[CLOUD OUTAGE - LOCAL ADAPTIVE MODE ACTIVE]**\n\nI have successfully re-architected a high-fidelity 7-day training split configured directly to bypass your active guardrails.\n\n### 🛑 ROUTINE CONFIGURATION GENERATED\nWould you like to sync this updated workout plan directly into your active Routine Builder board?"
                            
                            output_payload = {
                                "route_decision": "local_fallback",
                                "response": ai_response,
                                "require_approval": True,
                                "time_taken": round(time.time() - start_time, 2)
                            }
                        else:
                            system_prompt = f"You are FlexRoute Coach in offline mode. Context: {athlete_context}. Answer the query concisely. No JSON routines."
                            fallback_msg = [SystemMessage(content=system_prompt)] + list(state_messages) + [HumanMessage(content=user_input)]
                            response = local_survival_llm.invoke(fallback_msg)
                            output_payload = {
                                "route_decision": "local_fallback",
                                "response": f"⚠️ **[CLOUD OUTAGE - LOCAL OFFLINE MODE ACTIVE]**\n\n{response.content}",
                                "time_taken": round(time.time() - start_time, 2)
                            }
                            
                        try:
                            conn = sqlite3.connect(DB_PATH, timeout=10.0)
                            cursor = conn.cursor()
                            cursor.execute("SELECT injury_flags FROM athlete_profile WHERE id=?", (active_id,))
                            updated_flags_row = cursor.fetchone()
                            conn.close()
                            if updated_flags_row:
                                output_payload["refresh_dashboard"] = True
                                output_payload["new_injury_flags"] = json.loads(updated_flags_row[0])
                        except Exception as db_sync_err:
                            print(f"❌ Offline sync fault skipped: {db_sync_err}")

                        return output_payload
                    except Exception as offline_err:
                        print(f"❌ Fatal blackout sequence executed: {offline_err}")
                        return {
                            "route_decision": "error",
                            "response": "System blackout. Please retry in 60 seconds.",
                            "time_taken": round(time.time() - start_time, 2)
                        }
                else:
                    key_rotator.rotate()

    except Exception as e:
        print(f"\n🛑 [EngineWorker] Pipeline stopped or errored: {e}")
        return {"response": "Process failed or aborted.", "time_taken": 0}

# SERVER BOOT SCRIPT

if __name__ == "__main__":
    print("\n🚀 [FLEXROUTE BRAIN] Booting Local Server Engine on Port 8000...\n")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)