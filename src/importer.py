# src/importer.py
import os
import json
import base64
import sqlite3
from typing import Optional
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

# Import the Ollama client for local failover execution
from langchain_ollama import ChatOllama

load_dotenv()  # Injects API keys from .env file into memory

# Central Database Configuration path matching your graph configuration
DB_PATH = os.getenv("DB_PATH", "checkpoints.sqlite")

# 1. DEFINE THE JSON SCHEMA
class AthleteProfile(BaseModel):
    # Removed 'name' so the AI never hallucinates or extracts CSV junk
    athlete_type: str = Field(description="E.g., Powerlifter, Bodybuilder, Crossfitter, General Fitness")
    estimated_experience_level: str = Field(description="Beginner, Intermediate, or Advanced")
    favorite_exercises: list[str] = Field(description="Top 3-5 most frequently performed exercises")
    injury_or_fatigue_flags: list[str] = Field(description="List ANY notes indicating pain, tweaking, skipping sets, or injuries. If none, output 'None'.")
    general_summary: str = Field(description="A 2-sentence summary of how this athlete trains and eats based on the data.")

def encode_image(image_path: str) -> str:
    """Converts an image to a base64 string for the AI to 'see'."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def compact_logs_to_profile(file_path: str):
    print(f"\n--- [Log Importer] Ingesting raw file: {file_path} ---")
    
    if not os.path.exists(file_path):
        print(f"❌ Error: Could not find file at {file_path}")
        return

    # Determine if it's an image or a text/csv file
    file_ext = os.path.splitext(file_path)[1].lower()
    is_image = file_ext in ['.png', '.jpg', '.jpeg']
    
    # Construct the multimodal prompt
    prompt_text = """
    You are an expert sports scientist and data analyst. 
    Review the attached fitness tracking data (which could be a CSV log, a screenshot of an app, or messy handwritten notes).
    Analyze the exercises, weights, diet notes, and physical feedback.
    
    Extract the data into a precise psychological and physical profile. 
    PAY EXTREME ATTENTION to any mention of pain, tweaks, or injuries.
    """

    if is_image:
        print("-> Detected Image file. Preparing pixel bytes...")
        base64_image = encode_image(file_path)
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt_text},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
            ]
        )
    else:
        print("-> Detected Text/CSV file. Preparing text string matrix...")
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_text = f.read()
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt_text + f"\n\nRAW DATA:\n{raw_text}"}
            ]
        )

    result = None

    # PRIMARY CLOUD ENGINE (GEMINI 2.5 FLASH)

    try:
        print("--- [Tier 1] Booting Primary Cloud Vision Engine (Gemini 2.5 Flash) ---")
        primary_key = os.getenv("GOOGLE_API_KEY")
        if not primary_key:
            raise ValueError("Primary GOOGLE_API_KEY is missing from environment layout.")
            
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.1, google_api_key=primary_key)
        structured_llm = llm.with_structured_output(AthleteProfile)
        
        print("--- [Processing] Compressing data points with Primary Cloud Key... ---")
        result = structured_llm.invoke([message])
        print("✅ Tier 1 Execution Successful.")

    except Exception as tier1_error:
        print(f"⚠️ Tier 1 Throttled or Out of Quota! Trace Error: {tier1_error}")
        
        # CLOUD KEY ROTATION FALLBACK (BACKUP GEMINI KEY)

        backup_key = os.getenv("GOOGLE_API_KEY_BACKUP")
        if backup_key:
            try:
                print("--- [Tier 2] Swapping API Credentials -> Booting Backup Cloud Engine ---")
                llm_backup = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.1, google_api_key=backup_key)
                structured_llm_backup = llm_backup.with_structured_output(AthleteProfile)
                
                print("--- [Processing] Compressing data points with Backup Cloud Key... ---")
                result = structured_llm_backup.invoke([message])
                print("✅ Tier 2 Backup Cloud Execution Successful.")
            except Exception as tier2_error:
                print(f"⚠️ Tier 2 Backup Key also failed or exhausted: {tier2_error}")
        else:
            print("ℹ️ No Backup Cloud Key detected in .env system arrays. Skipping Tier 2.")

    # LOCAL HARDWARE SURVIVAL MODE (OLLAMA LOCAL LLM)

    if result is None:
        print("🔄 [Tier 3] Core Cloud Stack Depleted -> Hot-Swapping to Local Processing Engine ---")
        if is_image:
            print("❌ Local Fallback Boundary: Text models cannot read raw pixels natively.")
            print("To proceed with image logs locally, download 'ollama run llama3.2-vision'.")
            print("Stripping visual layout layers to prevent runtime fatal crashes...")
            message = HumanMessage(
                content=[{"type": "text", "text": prompt_text + "\n\n[Warning: Multi-modal layer parsed as blind text due to critical cloud outage]"}]
            )
        
        try:
            print("-> Triggering Local Ollama System Container (Model: mistral)...")
            local_llm = ChatOllama(model="mistral", temperature=0.0, format="json", base_url=OLLAMA_URL)
            local_structured = local_llm.with_structured_output(AthleteProfile)
            
            result = local_structured.invoke([message])
            print("✅ Tier 3 Local Micro-Engine Process Completed Successfully!")
        except Exception as local_error:
            print(f"❌ CRITICAL BLACKOUT: Cloud arrays and Local edge endpoints failed completely. Trace: {local_error}")
            return

    # RELATIONAL DATABASE ARCHIVE AND COMPACTION LAYER

    if result:
        try:
            print("--- [Database Sync] Inserting profile updates directly into SQLite ---")
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            try:
                cursor.execute("ALTER TABLE athlete_profile ADD COLUMN summary TEXT;")
                conn.commit()
            except sqlite3.OperationalError:
                pass 

            # Dynamically get the currently logged in user
            active_id = os.environ.get("ACTIVE_USER_ID", "current_user")

            # Lock the current name. We will NEVER let the AI change this.
            cursor.execute("SELECT name FROM athlete_profile WHERE id=?", (active_id,))
            row = cursor.fetchone()
            final_name = row[0] if row else active_id.replace("_", " ").title()
            
            injury_flags_json = json.dumps(result.injury_or_fatigue_flags if result.injury_or_fatigue_flags else ["None"])
            
            # Check if user exists. If yes: UPDATE. If no: INSERT new row.
            cursor.execute("SELECT id FROM athlete_profile WHERE id=?", (active_id,))
            exists = cursor.fetchone()

            if exists:
                cursor.execute("""
                    UPDATE athlete_profile 
                    SET athlete_type=?, experience_level=?, injury_flags=?, summary=?
                    WHERE id=?
                """, (result.athlete_type, result.estimated_experience_level, injury_flags_json, result.general_summary, active_id))
            else:
                cursor.execute("""
                    INSERT INTO athlete_profile (id, name, athlete_type, experience_level, injury_flags, summary)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (active_id, final_name, result.athlete_type, result.estimated_experience_level, injury_flags_json, result.general_summary))
            
            conn.commit()
            conn.close()
            
            print(f"\n✅ SUCCESS: Profile Attributes Synchronized for User: {active_id}")
            
        except Exception as db_e:
            print(f"❌ Database Transaction Fault Writing Profiles: {db_e}")

if __name__ == "__main__":
    # Test execution matching structural file allocations
    compact_logs_to_profile("6-Day-Gym-Workout-Schedule-Template-edit-online.png")
    