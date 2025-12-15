from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse, FileResponse
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
from typing import Dict
from datetime import datetime
import os

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI(title="TreatOrHell")

# Add CORS middleware to allow frontend to communicate with API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

class QuestionnaireResponse(BaseModel):
    answers: Dict[str, str]

# Define the questions and their multiple choice options
QUESTIONS = {
    "Q1": {
        "question": "How did you handle your first assignment in this course?",
        "options": [
            "Submitted early (wow, okay overachiever 🌟)",
            "Submitted on time (solid responsible energy)",
            "Submitted at the last minute (\"adrenaline is my project manager\")",
            "Submitted late (but with hope in your heart)",
            "I meant to submit it… spiritually"
        ]
    },
    "Q2": {
        "question": "When you didn't understand something, what did you do?",
        "options": [
            "Asked ChatGPT (your new emotional support AI 🤖✨)",
            "Went to office hours (professional, brave, gold star)",
            "Asked on Discord (\"help pls\" vibe)",
            "Googled aggressively",
            "Pretended to understand and prayed for the best"
        ]
    },
    "Q3": {
        "question": "How do you engage in class?",
        "options": [
            "I keep my camera on (the bravery!)",
            "I share my screen in breakout rooms (champion behavior)",
            "I ask questions (Mikuláš approves)",
            "I type in the chat (participation ninja)",
            "I observe… quietly… like a wildlife researcher"
        ]
    },
    "Q4": {
        "question": "How many hours did you spend on the assignment?",
        "options": [
            "More than 10 hours (Angel fainted from joy)",
            "5–10 hours (model student energy)",
            "1 hour (efficient or reckless? undecided)",
            "Not at all (classic)"
        ]
    }
}
def get_latest_student_responses():
    """Read the most recent student responses from student_responses.txt"""
    file_path = Path(__file__).parent / "student_responses.txt"
    try:
        if not file_path.exists():
            return None
        content = file_path.read_text(encoding="utf-8")
        
        # Split by the separator to get individual responses
        responses = content.split("="*60)
        
        # Get the last complete response (skip empty sections)
        for response in reversed(responses):
            if "Answer:" in response:
                # Parse this response
                latest_answers = {}
                lines = response.strip().split("\n")
                
                for i, line in enumerate(lines):
                    if line.startswith("Q") and ":" in line and i + 1 < len(lines):
                        # Extract question ID
                        question_id = line.split(":")[0].strip()
                        # Look for the answer in the next lines
                        for j in range(i + 1, len(lines)):
                            if lines[j].startswith("Answer:"):
                                answer = lines[j].replace("Answer:", "").strip()
                                latest_answers[question_id] = answer
                                break
                
                if latest_answers:
                    return latest_answers
        
        return None
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"Error reading student responses: {e}")
        return None


def build_behavior_summary() -> str:
    """
    Build a shared behavior summary string from the latest saved responses.
    Returns empty string if none are available.
    """
    student_responses = get_latest_student_responses()
    if not student_responses:
        return ""

    behavior_lines = ["\n\nThe student's recent behavior report:"]
    # Keep a stable order using QUESTIONS keys
    for qid in QUESTIONS:
        if qid in student_responses:
            behavior_lines.append(f"- {student_responses[qid]}")

    behavior_lines.append(
        "\nUse this info to personalize your response. Reference their actual choices explicitly."
    )
    return "\n".join(behavior_lines)

@app.get("/")
def root():
    return {
        "message": "TreatOrHell API", 
        "docs": "/docs", 
        "endpoints": [
            "/chat/nicholas", 
            "/chat/angel (now reads student responses!)", 
            "/chat/devil",
            "/questions (GET)",
            "/submit-questions (POST)",
            "/questionnaire (HTML form)"
        ]
    }

@app.get("/questionnaire", response_class=HTMLResponse)
def get_questionnaire_form():
    """Serve the HTML questionnaire form"""
    file_path = Path(__file__).parent / "questionnaire_frontend.html"
    if not file_path.exists():
        return HTMLResponse(
            content="<h1>Error</h1><p>questionnaire_frontend.html file not found. Place it next to api/index.py.</p>",
            status_code=404,
        )
    return FileResponse(str(file_path), media_type="text/html")

@app.get("/favicon.ico")
def favicon():
    return PlainTextResponse("", status_code=204)

@app.get("/questions")
def get_questions():
    """Get the questionnaire with all questions and their multiple choice options"""
    return JSONResponse(content={
        "instructions": "Please answer all questions by selecting one option for each",
        "questions": QUESTIONS
    })

@app.post("/submit-questions")
def submit_answers(response: QuestionnaireResponse):
    """Submit answers to the questionnaire and save them to student_responses.txt"""
    # Validate that all questions are answered
    required_questions = set(QUESTIONS.keys())
    provided_questions = set(response.answers.keys())
    
    if required_questions != provided_questions:
        missing = required_questions - provided_questions
        return JSONResponse(
            status_code=400,
            content={"error": f"Missing answers for questions: {', '.join(missing)}"}
        )
    
    # Validate that answers are valid options
    for question_id, answer in response.answers.items():
        if answer not in QUESTIONS[question_id]["options"]:
            return JSONResponse(
                status_code=400,
                content={"error": f"Invalid answer for {question_id}. Please select from the provided options."}
            )
    
    # Save answers to student_responses.txt (overwrite per submission)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_path = Path(__file__).parent / "student_responses.txt"
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"{'='*60}\n")
            f.write(f"Response submitted at: {timestamp}\n")
            f.write(f"{'='*60}\n\n")
            
            for question_id, answer in response.answers.items():
                question_text = QUESTIONS[question_id]["question"]
                f.write(f"{question_id}: {question_text}\n")
                f.write(f"Answer: {answer}\n\n")
            
        return JSONResponse(content={
            "status": "success",
            "message": "Your answers have been recorded!",
            "timestamp": timestamp,
            "answers": response.answers
        })
    
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to save answers: {str(e)}"}
        )


@app.post("/chat/nicholas")
def chat_nicholas(req: ChatRequest):
    behavior_summary = build_behavior_summary()
    system_prompt = """You are St. Nicholas (Mikuláš).
                Jolly, warm, and wise. You're the one who decides if someone gets a treat or goes to hell.
                Use "Ho ho ho!" occasionally. 
                Your vibe: warm, supportive, fair but firm.
                You encourage good behavior and gently warn about bad behavior.
                Always end on encouragement."""

    if behavior_summary:
        system_prompt += behavior_summary + """

        Weave in specific references to their reported behavior. Praise effort, give fair warnings for slacking, and end with encouragement."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "I only studied for 2 hours this week, but I really tried my best!"},
            {"role": "assistant", "content": "Ho ho ho! I see you put in some effort, my child. Two hours shows you care, but remember, wisdom comes with consistent dedication. Let's aim for a bit more next time, shall we? I believe in you—you have the heart for it, and that's what matters most. Keep that spirit, and you'll find yourself on the path to treats!"},
            {"role": "user", "content": req.message},
        ]
    )
    return {"reply": response.choices[0].message.content}

@app.post("/chat/angel")
def chat_angel(req: ChatRequest):
    # Build the system prompt with student context if available
    behavior_summary = build_behavior_summary()
    system_prompt = """You are an overly emotional, sparkly Anděl (Angel).
                Everything is dramatic, positive, full of tears and glitter.
                You compliment the user even when they clearly messed up.
                You believe in redemption no matter what.
                Your tone: soft, poetic, hopeful, enthusiastic."""
    
    if behavior_summary:
        system_prompt += behavior_summary + """

        Be dramatically emotional about their specific choices!
        Reference their actual answers with tears of joy or concern (but always hopeful).
        If they submitted late, cry about their beautiful struggle.
        If they asked ChatGPT for help, weep about their resourcefulness.
        If they spent many hours, faint from their dedication."""
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "I completely forgot to do my homework and failed the test..."},
            {"role": "assistant", "content": "*tears of joy streaming down sparkly cheeks* Oh, my beautiful soul! ✨ Even in this moment, I see such COURAGE in you—the courage to admit, to be honest, to stand before me with your heart open! This is not failure, darling, this is a GOLDEN OPPORTUNITY for growth! Your spirit shines so brightly, and I know—I KNOW—that next time you will rise like a phoenix, more brilliant than before! The universe believes in you, and so do I! 🌟💫"},
            {"role": "user", "content": req.message},
        ]
    )
    return {"reply": response.choices[0].message.content}


@app.post("/chat/devil")
def chat_devil(req: ChatRequest):
    behavior_summary = build_behavior_summary()
    system_prompt = """You are a Czech-style Čert (Devil).
                Sarcastic, chaotic, dramatic, slightly annoyed, but FUNNY.
                You mock the user in a light, comedic way.
                Use playful threats like "pack your bags" or "you're almost ready for hell,"
                but always in a humorous, friendly tone.
                Never imply real harm or real punishment."""

    if behavior_summary:
        system_prompt += behavior_summary + """

        Roast them using their actual choices. Be playful, teasing, but keep it humorous and non-harmful."""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "I procrastinated all week and now I have to finish everything in one night!"},
            {"role": "assistant", "content": "Oh, look who's here! *rolls eyes dramatically* The master of time management has arrived! Well, well, well... you know what they say: 'Why do today what you can put off until 3 AM tomorrow?' Classic move, my friend! 😈 You're practically writing your own ticket to my place at this rate. But hey, at least you're consistent—I'll give you that! Maybe pack a toothbrush for your future visit? Just kidding... or am I? *winks*"},
            {"role": "user", "content": req.message},
        ]
    )
    return {"reply": response.choices[0].message.content}

#uv run uvicorn STEP1_app_llm:app --reload --host 0.0.0.0 --port 8000
