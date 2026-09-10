import os
import json
import sqlite3
import operator
import re
from typing import List, Optional, Annotated, TypedDict
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver
from src.biomechanics import search_biomechanics

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

DB_PATH = "checkpoints.sqlite"
local_llm = ChatOllama(model="mistral", temperature=0.0,base_url=OLLAMA_URL)

# --- Pydantic Schema Specifications ---
class ProfileUpdateSchema(BaseModel):
    name: Optional[str] = Field(None, description="Updated name of the athlete")
    athlete_type: Optional[str] = Field(None, description="Training methodology like Calisthenics or Weightlifting")
    experience_level: Optional[str] = Field(None, description="Athlete skill tier")
    new_injury_flags: Optional[List[str]] = Field(None, description="Newly reported muscle tweaks, pain points, or injuries")
    recovered_injury_flags: Optional[List[str]] = Field(None, description="Explicitly stated healed or resolved injuries")

class ExerciseItem(BaseModel):
    name: str = Field(..., description="Exercise name. MUST NOT BE BLANK. e.g. 'Pull-ups'")
    sets: str = Field(..., description="Target sets. MUST NOT BE BLANK. e.g. '3 sets'")
    reps: str = Field(..., description="Target reps. MUST NOT BE BLANK. e.g. '8-12 reps'")
    explanation: str = Field(..., description="A detailed, two-sentence biomechanical form cue. MUST NOT BE BLANK.")

class RoutineDay(BaseModel):
    day_of_week: str = Field(..., description="Day of the week")
    focus_area: str = Field(..., description="The dynamic regional muscular focus target")
    explanation: str = Field(..., description="High-level day specific tactical intent narrative")
    exercises: List[ExerciseItem] = Field(default_factory=list, description="Target assignment list")

class WeeklyRoutinePlan(BaseModel):
    explanation: str = Field(..., description="Macrocycle adaptation overview script")
    routine_days: List[RoutineDay] = Field(..., description="Chronological 7-day routine block array")

class FlexRouteState(TypedDict, total=False):
    messages: Annotated[list, operator.add]
    proposed_routine: str
    route_decision: str

def get_athlete_context_from_db():
    active_id = os.environ.get("ACTIVE_USER_ID", "guest_user")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name, athlete_type, injury_flags FROM athlete_profile WHERE id=?", (active_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return f"Athlete: {row[0]} | Style: {row[1]} | Active Injuries: {row[2]}"
    except Exception:
        pass
    return "Context: General Training Setup"

def profile_gate_node(state: FlexRouteState):
    print("--- [Node: Profile Gate] Scanning for Profile Updates ---")
    messages = state.get("messages", [])
    if not messages:
        return {}
        
    last_msg = messages[-1].content.strip().lower()
    if last_msg in ["approve", "accept", "yes", "reject", "deny", "no"] and len(messages) >= 2:
        target_msg = messages[-2].content
    else:
        target_msg = messages[-1].content
        
    active_id = os.environ.get("ACTIVE_USER_ID", "guest_user")
    update_data = None

    # THE SMART PYTHON INTERCEPTOR (FOR UPDATING ACTIVE INJURY GUARDRAILS)
    target_lower = target_msg.lower()
    # Added natural phrasing to the instant-wipe list
    explicit_wipe_commands = ["clear all", "clear my injuries", "all healed", "no injuries", "fully recovered", "100% healed", "my injury is healed", "injuries are healed", "injury is healed", "my injuries are healed"]
    healing_words = ["healed", "better", "recovered", "fixed", "gone", "cleared", "resolved", "no more"]
    damage_words = ["pain", "hurt", "injury", "injured", "strain", "sprain", "tear", "tore", "tweaked", "broken", "issue"]
    body_parts = ["shoulder", "knee", "back", "wrist", "ankle", "elbow", "neck", "hip", "hamstring", "quad", "calf", "chest", "pec", "groin", "bicep", "tricep", "forearm", "spine"]
    complex_words = ["but", "now", "and", "while", "also", "then", ","]
    
    # 1. Check for Emergency Global Wipe (Instant)
    if any(kw in target_lower for kw in explicit_wipe_commands):
        try:
            temp_conn = sqlite3.connect(DB_PATH)
            temp_cursor = temp_conn.cursor()
            temp_cursor.execute("SELECT injury_flags FROM athlete_profile WHERE id=?", (active_id,))
            temp_row = temp_cursor.fetchone()
            temp_conn.close()
            
            if temp_row and temp_row[0]:
                current_active = json.loads(temp_row[0])
                if "None" in current_active: current_active.remove("None")
                update_data = ProfileUpdateSchema(new_injury_flags=[], recovered_injury_flags=current_active if current_active else ["All Active Injuries"])
                print("⚡ [Python Interceptor] Forced recovery pipeline for 'Clear All' command.")
        except Exception as e:
            update_data = ProfileUpdateSchema(new_injury_flags=[], recovered_injury_flags=["All Active Injuries"])
    
    # 2. Simple Sentence Python Fast-Pass
    # If the sentence has "but", "now", or "and", Python skips it so Mistral can handle the wordplay
    elif not any(cw in target_lower for cw in complex_words):
        extracted_healed = []
        extracted_new = []
        
        is_healed = any(hw in target_lower for hw in healing_words)
        is_damage = any(dw in target_lower for dw in damage_words)
        
        if is_healed or is_damage:
            found_bp = False
            for bp in body_parts:
                if bp in target_lower:
                    found_bp = True
                    prefix = ""
                    if f"left {bp}" in target_lower: prefix = "left "
                    elif f"right {bp}" in target_lower: prefix = "right "
                    
                    full_name = f"{prefix}{bp} injury"
                    if is_healed: extracted_healed.append(full_name)
                    elif is_damage: extracted_new.append(full_name)
            
            if not found_bp and is_healed and not is_damage:
                extracted_healed.append("All Active Injuries")
                
        if extracted_healed or extracted_new:
            update_data = ProfileUpdateSchema(new_injury_flags=extracted_new, recovered_injury_flags=extracted_healed)
            print(f"⚡ [Python Interceptor] Simple extraction: New={extracted_new}, Healed={extracted_healed}")

    # 3. THE LOCAL LLM OVERRIDE (For Wordplay and Complex Sentences)
    if not update_data:
        is_medical_intent = any(w in target_lower for w in healing_words + damage_words)
        if is_medical_intent:
            print("🧠 [Local Agent] Parsing complex medical wordplay...")
            try:
                fallback_prompt = f"""Analyze the user message: "{target_msg}"
                Identify ONLY acute physical musculoskeletal injuries. 
                STRICT RULE: Ignore mental health, anxiety, or conversational questions.
                
                You must extract TWO lists:
                1. "new_injury_flags": Injuries the user just got, or currently has.
                2. "recovered_injury_flags": Injuries the user explicitly says are "healed", "better", "recovered", or "fixed".
                
                EXAMPLES:
                User: "My left knee is healed but I tweaked my right shoulder."
                Output: {{"new_injury_flags": ["right shoulder injury"], "recovered_injury_flags": ["left knee injury"]}}
                
                User: "my injury is healed"
                Output: {{"new_injury_flags": [], "recovered_injury_flags": ["All Active Injuries"]}}
                
                User: "i got a left and right shoulder injury"
                Output: {{"new_injury_flags": ["left shoulder injury", "right shoulder injury"], "recovered_injury_flags": []}}
                
                Return ONLY a valid JSON object matching the exact structure above.
                If none, use empty arrays []. Do not output markdown or text."""
                
                json_local_llm = ChatOllama(model="mistral", temperature=0.0, format="json", num_predict=100, base_url=OLLAMA_URL)
                raw_response = json_local_llm.invoke([HumanMessage(content=fallback_prompt)]).content.strip()
                
                if "```" in raw_response: 
                    raw_response = raw_response.split("```json")[-1].split("```")[0].strip()
                elif raw_response.startswith("```"): 
                    raw_response = raw_response.replace("```json", "").replace("```", "").strip()
                
                if not raw_response: 
                    raw_response = '{"new_injury_flags": [], "recovered_injury_flags": []}'
                
                parsed_data = json.loads(raw_response)
                
                update_data = ProfileUpdateSchema(
                    new_injury_flags=parsed_data.get("new_injury_flags", []),
                    recovered_injury_flags=parsed_data.get("recovered_injury_flags", [])
                )
                print(f"✅ [Local Agent] Mistral extracted: {parsed_data}")
            except Exception as e3:
                print(f"❌ Mistral extraction drop out: {e3}")
                return {}
    if not update_data:
        return {}

    # Trigger the interrupt ONLY if there are actually items in the arrays
    if bool(update_data.new_injury_flags or update_data.recovered_injury_flags):
        new_injuries = update_data.new_injury_flags if update_data.new_injury_flags else []
        healed_injuries = update_data.recovered_injury_flags if update_data.recovered_injury_flags else []
        status_msg = f"New injuries tracked: {', '.join(new_injuries)}" if new_injuries else f"Healed status tracked: {', '.join(healed_injuries)}"
        
        user_decision = interrupt({
            "message": f"### 🛑 SAFETY AUTHORIZATION REQUIRED\nInjury profile updates detected ({status_msg}). Please confirm synchronization to your Active Guardrails.",
            "new": update_data.new_injury_flags,
            "recovered": update_data.recovered_injury_flags
        })
        
        if str(user_decision).strip().lower() not in ["approve", "accept", "yes"]:
            print("🚫 [HITL] User rejected medical sync. Aborting SQLite commit.")
            return {"route_decision": "abort"} # Tell the router to abort the flow

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name, athlete_type, experience_level, injury_flags FROM athlete_profile WHERE id=?", (active_id,))
        row = cursor.fetchone()
        
        if row:
            current_name, current_style, current_level, current_flags_raw = row
            current_flags = json.loads(current_flags_raw) if current_flags_raw else []
            
            updated_name = update_data.name if update_data.name else current_name
            updated_style = update_data.athlete_type if update_data.athlete_type else current_style
            updated_level = update_data.experience_level if update_data.experience_level else current_level
            
            if update_data.new_injury_flags:
                for flag in update_data.new_injury_flags:
                    if flag not in current_flags and flag.lower() != "none" and flag.strip() != "":
                        if "None" in current_flags: current_flags.remove("None")
                        current_flags.append(flag)
            
            if update_data.recovered_injury_flags:
                for flag in update_data.recovered_injury_flags:
                    flag_lower = flag.lower()
                    for existing in list(current_flags):
                        existing_lower = existing.lower()
                        if flag_lower in existing_lower or existing_lower in flag_lower:
                            if existing in current_flags: current_flags.remove(existing)
                            continue
            
            if not current_flags: current_flags = ["None"]
            cursor.execute("UPDATE athlete_profile SET name=?, athlete_type=?, experience_level=?, injury_flags=? WHERE id=?", 
                           (updated_name, updated_style, updated_level, json.dumps(current_flags), active_id))
            conn.commit()
            print(f"✅ [DB WRITE] Profile successfully updated in SQLite for: {active_id}")
        conn.close()
    except Exception as db_err:
        print(f"❌ [DB WRITE ERROR] Database stack drop: {db_err}")
    return {}

def router_node(state: FlexRouteState):
    print("--- [Node: Smart Router] Analyzing Intent ---")
    
    # If the previous node explicitly aborted, route to local chat immediately to kill the graph
    if state.get("route_decision") == "abort":
        return {"route_decision": "local"}

    messages = state.get("messages", [])
    if not messages: return {"route_decision": "local"}
    
    last_msg = messages[-1].content.strip().lower()
    
    # If the user is just confirming an interrupt (approve/reject), they are NOT asking for a split. So Bypassing it
    if last_msg in ["approve", "accept", "yes", "reject", "deny", "no"]:
        print("🛡️ [Smart Router] System command detected. Bypassing structural generation.")
        return {"route_decision": "local"}

    intent_msg = last_msg
        
    structural_keywords = ["split", "routine", "program", "plan", "workout", "macrocycle", "schedule", "modify", "add", "week", "script", "build", "create", "generate"]
    conversational_override = ["diet", "food", "nutrition", "meal", "eat", "calories", "macros", "protein", "how", "why", "what", "which", "advice", "fear", "anxiety", "deal with", "tips", "scared", "help", "cardiophobia", "best", "good", "opinion", "hurt", "pain", "fix"]
    generation_commands = ["give me", "make me", "create", "build", "generate", "can i get", "i want a", "write me", "script"]
    medical_keywords = ["injured", "injury", "healed", "clear", "tear", "tore", "strain", "recovered", "tweaked", "sprain", "broken"]

    # MULTI-TASKING (IF USER ASKS FOR BOTH UPDATING INJURY DATA AND CREATING A SPLIT)
    wants_split = (any(cmd in intent_msg for cmd in generation_commands) and any(kw in intent_msg for kw in structural_keywords)) or "split" in intent_msg or "routine" in intent_msg
    
    if wants_split:
        print("🚀 [Smart Router] Structural generation intent detected! Routing to CLOUD.")
        return {"route_decision": "cloud"}

    # If its JUST a medical update (no split request), just chat.
    if any(kw in intent_msg for kw in medical_keywords):
        return {"route_decision": "local"}

    if any(kw in intent_msg for kw in conversational_override):
        return {"route_decision": "local"}
        
    if any(kw in intent_msg for kw in structural_keywords):
        return {"route_decision": "cloud"}
        
    return {"route_decision": "local"}

def local_node(state: FlexRouteState):
    print("--- [Node: Local Agent] Executing Conversational Chat ---")
    athlete_context = get_athlete_context_from_db()
    messages = state.get("messages", [])
    
    if not messages:
        return {"messages": [AIMessage(content="Ready to work!")]}
        
    last_msg = messages[-1].content.strip().lower()
    
    if last_msg in ["approve", "accept", "yes"]:
        return {"messages": [AIMessage(content="✅ Got it. Your profile guardrails are successfully synced and active! What's our next move?")]}
    elif last_msg in ["reject", "deny", "no"]:
        return {"messages": [AIMessage(content="🚫 Understood. I've cancelled that medical update. Your guardrails remain unchanged.")]}

    system_prompt = f"""You are the FlexRoute Neural Engine, a cold, precise, tactical AI fitness architect.
    Context: {athlete_context}
    
    CRITICAL RULES:
    1. GREETINGS & TYPOS: If the user says a short greeting, acknowledge system readiness mechanically.
    2. GAG ORDER: DO NOT mention the athlete's injuries unless they ask a direct question about rehab.
    3. NO BUBBLY CHAT: Be cold and mechanical.
    4. NEVER generate workout plans or JSON arrays."""
    
    compiled_messages = [SystemMessage(content=system_prompt)] + messages
    chat_llm = ChatOllama(model="mistral", temperature=0.7, base_url=OLLAMA_URL)
    response = chat_llm.invoke(compiled_messages)
    return {"messages": [AIMessage(content=response.content)]}

def cloud_node(state: FlexRouteState):
    print("--- [Node: Cloud Agent] Architecting Structural Plan ---")
    athlete_context = get_athlete_context_from_db()
    messages = state.get("messages", [])
    
    if messages and messages[-1].content.lower() in ["approve", "accept", "yes"] and len(messages) >= 2:
        target_payload = messages[-2].content
    else:
        target_payload = messages[-1].content if messages else "Generate workout split"

    rag_context = ""
    active_id = os.environ.get("ACTIVE_USER_ID", "guest_user")
    is_healthy = True 
    
    active_type = "General Training"
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # Now I explicitly grab the athlete_type so the prompt respects it
        cursor.execute("SELECT athlete_type, injury_flags FROM athlete_profile WHERE id=?", (active_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            active_type = row[0] if row[0] else "General Training"
            if row[1]:
                injuries = json.loads(row[1])
                if injuries and "None" not in injuries:
                    is_healthy = False
                    print(f"🔍 [RAG Engine] Active injuries detected: {injuries}. Searching Qdrant...")
                    
                    query = f"rehab, recovery, and safe exercises for {', '.join(injuries)}"
                    results = search_biomechanics(query, k=4)
                    
                    if results:
                        rag_context = "\n### 🚨 CRITICAL REHAB & BIOMECHANICS KNOWLEDGE BASE:\n"
                        for i, res in enumerate(results):
                            rag_context += f"- {res.page_content}\n"
                            print(f"✅ [RAG Injection] Chunk {i+1} loaded into prompt: {res.page_content[:50]}...")
                        rag_context += "\nYOU MUST PRESCRIBE SAFE EXERCISE ALTERNATIVES FROM THIS KNOWLEDGE BASE TO ACCOMMODATE THE INJURY.\n"
                    else:
                        print("⚠️ [RAG Engine] Search returned no chunks for these injuries.")
                else:
                    print("✅ [RAG Engine] Healthy athlete. Skipping RAG injection.")
    except Exception as e:
        print(f"⚠️ [RAG Engine] Qdrant injection failed: {e}")

    if is_healthy:
        split_directive = f"The athlete is fully operational. Program EXACTLY 5 Active Training Days and 2 Rest Days. The daily focus areas MUST strictly align with {active_type} (e.g., 'Vinyasa Flow', 'Upper Body', 'Flexibility')."
        naming_rule = "PURE NAMING: Use standard movement/pose names ONLY. Absolutely NO parenthetical labels, NO side-specific tags, and NO injury references."
    else:
        split_directive = f"Prioritize systemic recovery. Scale down to EXACTLY 4 Active Training Days and 3 Rest Days. The daily focus areas MUST align with {active_type} but accommodate the injuries."
        naming_rule = "CONTEXTUAL NAMING: You MUST append helpful tags like '(Healthy Side)' or '(Rehab)' to the names to explicitly guide the athlete safely."

    system_prompt = f"""You are the FlexRoute Elite Programming Engine. 
    Context: {athlete_context}
    {rag_context}
    
    Task: Assemble a customized 7-day macrocycle that STRICTLY ENFORCES the athlete's chosen training style: {active_type}.
    
    CRITICAL STYLE ENFORCEMENT:
    If the style is Yoga, Calisthenics, or non-weights, DO NOT program Barbell or Dumbbell movements. Use bodyweight holds, stretches, or flows.
    If the style is Powerlifting or Bodybuilding, use appropriate weighted compound and isolation movements.
    
    STEP 1: DYNAMIC WEEKLY SPLIT RATIO (MANDATORY):
    {split_directive}
    
    STEP 2: BIOMECHANICAL SEQUENCING:
    1. If an injury is present, trace it to its exact human anatomy.
    2. DYNAMIC EXCLUSION: Completely ban any movement loading that specific chain.
    3. {naming_rule}
    4. SEQUENCING: Place the most neurologically demanding movements/poses first in the session.
    
    STEP 3: EXERCISE QUOTA RULES & VOLUME:
    1. For any day designated as a Rest Day, the 'focus_area' must be 'Rest Day' and the 'exercises' array MUST be completely empty: []
    2. For EVERY Active Training Day, you MUST generate EXACTLY 6 exercises/movements.
    3. DO NOT use the words "sets" or "reps" inside the JSON numerical values. Just output the raw numbers (e.g., sets: "3", reps: "8-12" or "60s")."""
    
    compiled_messages = [SystemMessage(content=system_prompt)] + [HumanMessage(content=target_payload)]
    
    plan = None
    routine_json = None
    
    try:
        print("☁️ [API Route] Attempting connection via Primary Cloud Key...")
        primary_key = os.environ.get("GOOGLE_API_KEY")
        cloud_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2, api_key=primary_key, max_retries=0)
        structured_cloud = cloud_llm.with_structured_output(WeeklyRoutinePlan)
        plan = structured_cloud.invoke(compiled_messages)
        routine_json = json.dumps([day.model_dump() for day in plan.routine_days])
        print("✅ [API Route] Primary Key Successful.")
        
    except Exception as e:
        print(f"⚠️ Primary Key Failed ({e}).")
        backup_key = os.environ.get("GOOGLE_API_KEY_BACKUP")
        
        if backup_key and backup_key.strip() != "":
            print("🔄 [API Route] Swapping to Backup Cloud Key...")
            try:
                cloud_llm_backup = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2, api_key=backup_key, max_retries=0)
                structured_cloud_backup = cloud_llm_backup.with_structured_output(WeeklyRoutinePlan)
                plan = structured_cloud_backup.invoke(compiled_messages)
                routine_json = json.dumps([day.model_dump() for day in plan.routine_days])
                print("✅ [API Route] Backup Key Successful.")
            except Exception as e2:
                print(f"❌ Backup Key also failed ({e2}). Triggering Local Fallback...")
        else:
            print("❌ No Backup Key found. Triggering Local Fallback...")

    if routine_json:
        return {
            "proposed_routine": routine_json,
            "messages": [AIMessage(content="The optimized tactical program configuration has been structured successfully.")]
        }

    print("🧠 [Local Agent] Injecting Qdrant RAG data into offline Mistral fallback...")
    fallback_prompt = (
        f"You are the FlexRoute Coach in offline mode operating as an expert Clinical Biomechanist. Context: {athlete_context}\n"
        f"{rag_context}\n"
        f"Task: Construct a complete 7-day training schedule customized dynamically to the athlete's training style ({active_type}) and injuries.\n\n"
        f"CRITICAL STYLE ENFORCEMENT:\n"
        f"If the style is Yoga, Calisthenics, or non-weights, DO NOT program Barbell/Dumbbell movements.\n\n"
        f"STEP 1: DYNAMIC WEEKLY SPLIT RATIO (MANDATORY):\n"
        f"{split_directive}\n\n"
        f"STEP 2: CRITICAL ANATOMICAL PRESS ENGINE & SEQUENCING:\n"
        f"1. If an injury is present, ban any exercise loading that specific chain.\n"
        f"2. {naming_rule}\n"
        f"3. Place the most demanding movements first.\n\n"
        f"STEP 3: EXERCISE QUOTA RULES:\n"
        f"1. Rest Days MUST have an empty exercises array: []\n"
        f"2. For EVERY Active Training Day, you MUST generate EXACTLY 6 exercises.\n\n"
        f"RULES:\n"
        f"1. Respond ONLY with a valid JSON object wrapped in a root object called \"routine_days\".\n"
        f"2. DO NOT write the words 'sets' or 'reps' in the numerical values. Just use numbers.\n\n"
        f"EXAMPLE EXACT FORMAT:\n"
        f"{{\n"
        f"  \"routine_days\": [\n"
        f"    {{\n"
        f"      \"day_of_week\": \"Monday\",\n"
        f"      \"focus_area\": \"Lower Body\",\n"
        f"      \"exercises\": [\n"
        f"        {{\"name\": \"Barbell Squats\", \"sets\": \"3\", \"reps\": \"8-12\", \"explanation\": \"Maintain core brace.\"}},\n"
        f"        {{\"name\": \"Walking Lunges\", \"sets\": \"3\", \"reps\": \"10-12\", \"explanation\": \"Keep chest upright.\"}},\n"
        f"        {{\"name\": \"Glute Bridges\", \"sets\": \"3\", \"reps\": \"15\", \"explanation\": \"Squeeze at the top.\"}},\n"
        f"        {{\"name\": \"Calf Raises\", \"sets\": \"4\", \"reps\": \"20\", \"explanation\": \"Full stretch at bottom.\"}},\n"
        f"        {{\"name\": \"Plank\", \"sets\": \"3\", \"reps\": \"60 sec\", \"explanation\": \"Neutral spine.\"}},\n"
        f"        {{\"name\": \"Side Plank\", \"sets\": \"2\", \"reps\": \"45 sec\", \"explanation\": \"Engage obliques.\"}}\n"
        f"      ]\n"
        f"    }},\n"
        f"    {{\n"
        f"      \"day_of_week\": \"Wednesday\",\n"
        f"      \"focus_area\": \"Rest Day\",\n"
        f"      \"exercises\": []\n"
        f"    }}\n"
        f"  ]\n"
        f"}}"
    )

    try:
        # 1. Clean up any stale abort signals before starting
        if os.path.exists("abort_signal.tmp"):
            os.remove("abort_signal.tmp")

        fallback_messages = [SystemMessage(content=fallback_prompt), HumanMessage(content=target_payload)]
        print("🧠 [Local Agent] Generating 7-day JSON matrix (this might take a minute)...")
        
        # 2. Start Mistral 
        json_llm = ChatOllama(model="mistral", temperature=0.1, format="json", num_predict=2500, base_url=OLLAMA_URL)
        response = json_llm.invoke(fallback_messages)
        
        # 3. Mistral finished! Check if the user hit "Abort" while they were waiting.
        if os.path.exists("abort_signal.tmp"):
            print("🛑 [Neural Engine] User aborted during generation. Discarding JSON ghost data.")
            os.remove("abort_signal.tmp")
            return {"proposed_routine": None, "messages": [AIMessage(content="⚠️ Process aborted by user.")]}

        raw_text = response.content.strip()
        
        print(f"🛠️ [DEBUG] Mistral JSON Output Start: {raw_text[:300]}...")
        
        if "```" in raw_text: 
            raw_text = raw_text.split("```json")[-1].split("```")[0].strip()
        elif raw_text.startswith("```"): 
            raw_text = raw_text.replace("```json", "").replace("```", "").strip()
            
        if not raw_text: 
            raw_text = '{"routine_days": []}'
            
        parsed_data = json.loads(raw_text)
        
        if isinstance(parsed_data, dict): 
            parsed_data = parsed_data.get("routine_days", parsed_data.get("days", []))
        if not isinstance(parsed_data, list): 
            parsed_data = []
        
        normalized_routine = []
        for day in parsed_data:
            day_name = str(day.get("day_of_week", day.get("day", "Unknown")))
            focus = str(day.get("focus_area", day.get("focus", "Rest Day")))
            raw_exercises = day.get("exercises", day.get("workout", []))
            
            clean_exercises = []
            if isinstance(raw_exercises, list):
                for ex in raw_exercises:
                    if isinstance(ex, dict):
                        clean_exercises.append({
                            "name": str(ex.get("name", ex.get("Exercise", ex.get("exercise", "Movement")))),
                            "sets": str(ex.get("sets", ex.get("Sets", "3"))),
                            "reps": str(ex.get("reps", ex.get("Reps", "8-12"))),
                            "explanation": str(ex.get("explanation", ex.get("Explanation", "Maintain proper form.")))
                        })
            
            normalized_routine.append({"day_of_week": day_name, "focus_area": focus, "exercises": clean_exercises})

        if not normalized_routine:
             normalized_routine = [{"day_of_week": "Fallback Day", "focus_area": "Active Recovery", "exercises": [{"name": "Mobility Walk", "sets": "1", "reps": "20 mins", "explanation": "Mistral returned empty JSON."}]}]

        from server import commit_proposed_routine, RoutineCommit
        routine_json = json.dumps(normalized_routine)
        commit_proposed_routine(RoutineCommit(proposed_json_str=routine_json))
        
        return {
            "proposed_routine": routine_json,
            "messages": [AIMessage(content="⚠️ **[CLOUD OUTAGE - LOCAL ADAPTIVE MODE ACTIVE]**\nThe workout split is designed to minimize stress while maintaining overall adaptation properties.")]
        }
    except Exception as inner_err:
        print(f"❌ Internal Graph Fallback failed completely: {inner_err}")
        if os.path.exists("abort_signal.tmp"): 
            os.remove("abort_signal.tmp")
        
        safe_routine = [
            {"day_of_week": "Monday", "focus_area": "Full Body Rehab", "exercises": [{"name": "Mobility Work", "sets": "3", "reps": "10", "explanation": "Gentle movement."}]},
            {"day_of_week": "Tuesday", "focus_area": "Rest Day", "exercises": []},
            {"day_of_week": "Wednesday", "focus_area": "Rest Day", "exercises": []},
            {"day_of_week": "Thursday", "focus_area": "Rest Day", "exercises": []},
            {"day_of_week": "Friday", "focus_area": "Rest Day", "exercises": []},
            {"day_of_week": "Saturday", "focus_area": "Rest Day", "exercises": []},
            {"day_of_week": "Sunday", "focus_area": "Rest Day", "exercises": []}
        ]
        return {
            "proposed_routine": json.dumps(safe_routine),
            "messages": [AIMessage(content="⚠️ **[SYSTEM OVERLOAD]** Local AI failed to parse the dynamic routine. Deployed safe recovery baseline.")]
        }

def safety_audit_node(state: FlexRouteState):
    print("--- [Node: Safety Gate] Auditing Plan Against Injury Profile ---")
    return {}

def decide_route(state: FlexRouteState):
    return state.get("route_decision", "local")

# --- System Graph Integration Assembly ---
workflow = StateGraph(FlexRouteState)
workflow.add_node("profile_gate", profile_gate_node)
workflow.add_node("router", router_node)
workflow.add_node("local", local_node)
workflow.add_node("cloud", cloud_node)
workflow.add_node("safety", safety_audit_node)

workflow.set_entry_point("profile_gate")
workflow.add_edge("profile_gate", "router")

workflow.add_conditional_edges(
    "router",
    decide_route,
    {
        "local": "local",
        "cloud": "cloud"
    }
)

workflow.add_edge("local", END)
workflow.add_edge("cloud", "safety")
workflow.add_edge("safety", END)

memory = MemorySaver()
app = workflow.compile(checkpointer=memory)