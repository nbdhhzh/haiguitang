import os
import uuid
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from openai import AsyncOpenAI
from dotenv import load_dotenv

from .database import get_db, engine, Base
from .models import User, Puzzle, GameSession, Interaction

load_dotenv()

app = FastAPI()

# CORS configuration
origins = [
    "*", 
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenRouter Client
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

MODEL_NAME = "google/gemini-2.0-flash-exp"

# Mount Static & Templates
app.mount("/static", StaticFiles(directory="server/static"), name="static")
templates = Jinja2Templates(directory="server/templates")

# --- Pydantic Models ---
class UserLogin(BaseModel):
    id: Optional[str] = None
    nickname: Optional[str] = None

class ChatRequest(BaseModel):
    session_id: int
    message: str

class RatingRequest(BaseModel):
    session_id: int
    rating: int

# --- API Endpoints ---

@app.post("/api/auth/login")
def login(user_data: UserLogin, db: Session = Depends(get_db)):
    user_id = user_data.id
    if not user_id:
        user_id = str(uuid.uuid4())
        user = User(id=user_id, nickname=user_data.nickname)
        db.add(user)
        db.commit()
    else:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            # Re-create if missing (e.g. DB reset)
            user = User(id=user_id, nickname=user_data.nickname)
            db.add(user)
            db.commit()
        elif user_data.nickname and user.nickname != user_data.nickname:
            user.nickname = user_data.nickname
            db.commit()
    return {"id": user_id, "nickname": user.nickname}

@app.get("/api/puzzles")
def get_puzzles(user_id: str, db: Session = Depends(get_db)):
    puzzles = db.query(Puzzle).all()
    result = []
    for p in puzzles:
        # Check status
        session = db.query(GameSession).filter(
            GameSession.user_id == user_id, 
            GameSession.puzzle_id == p.id
        ).first()
        
        status = "new"
        if session:
            status = session.status
        
        # Create a preview of the content (first sentence or 30 chars)
        preview = p.content
        if preview:
            # Try to cut at the first punctuation
            import re
            match = re.search(r'[。！？.!?]', preview)
            if match:
                preview = preview[:match.end()]
            else:
                preview = preview[:30] + "..."
            
        result.append({
            "id": p.id,
            "title": p.title,
            "status": status,
            "preview": preview
        })
    return result

@app.get("/api/puzzles/{puzzle_id}")
def get_puzzle_detail(puzzle_id: int, user_id: str, db: Session = Depends(get_db)):
    puzzle = db.query(Puzzle).filter(Puzzle.id == puzzle_id).first()
    if not puzzle:
        raise HTTPException(status_code=404, detail="Puzzle not found")
    
    # Get or Create Session
    session = db.query(GameSession).filter(
        GameSession.user_id == user_id, 
        GameSession.puzzle_id == puzzle_id
    ).first()
    
    if not session:
        session = GameSession(user_id=user_id, puzzle_id=puzzle_id)
        db.add(session)
        db.commit()
        db.refresh(session)
        
    # Get History
    history = db.query(Interaction).filter(Interaction.session_id == session.id).order_by(Interaction.timestamp).all()
    
    return {
        "puzzle": {
            "id": puzzle.id,
            "title": puzzle.title,
            "content": puzzle.content,
            # Truth is NOT sent here
        },
        "session": {
            "id": session.id,
            "status": session.status,
            "rating": session.rating
        },
        "history": [{"role": h.role, "content": h.content} for h in history]
    }

@app.post("/api/game/chat")
async def chat(req: ChatRequest, db: Session = Depends(get_db)):
    session = db.query(GameSession).filter(GameSession.id == req.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    puzzle = session.puzzle
    
    # Save User Message
    user_interaction = Interaction(session_id=session.id, role="user", content=req.message)
    db.add(user_interaction)
    db.commit()
    
    # Build Prompt
    system_prompt = f"""
You are the host of a Lateral Thinking Puzzle (Turtle Soup) game.
Puzzle: {puzzle.content}
Truth: {puzzle.truth}

Your goal is to answer the user's questions to help them solve the puzzle.
Rules:
1. Only answer with "Yes", "No", or "Irrelevant".
2. If the user's question assumes something wrong, you can say "No".
3. If the user guesses the core truth correctly, you can confirm it and congratulate them.
4. Do NOT reveal the truth directly unless the user has effectively solved it.
5. Be concise.
    """
    
    # Fetch recent history (limit context window if needed, here we take all)
    history_objs = db.query(Interaction).filter(Interaction.session_id == session.id).order_by(Interaction.timestamp).all()
    messages = [{"role": "system", "content": system_prompt}]
    for h in history_objs:
        # Convert internal role to API role
        role = "assistant" if h.role == "ai" else "user"
        messages.append({"role": role, "content": h.content})
        
    try:
        completion = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            
        )
        ai_response = completion.choices[0].message.content
        
        # --- Safety/Legality Check ---
        is_legal = True
        
        # 1. Length Check
        if len(ai_response) > 500: 
             is_legal = False # Too long for a Yes/No game
             
        # 2. Keyword Check (Simple safeguard)
        forbidden_terms = ["汤底", "真相", "The truth is", "Answer:"]
        if any(term in ai_response for term in forbidden_terms):
             is_legal = False
             
        # Save AI Response
        ai_interaction = Interaction(
            session_id=session.id, 
            role="ai", 
            content=ai_response,
            is_legal=is_legal
        )
        db.add(ai_interaction)
        db.commit()
        
        if not is_legal:
            return {"role": "ai", "content": "The host remains silent. (Response filtered for safety)"}

        return {"role": "ai", "content": ai_response}
        
    except Exception as e:
        # Log error
        print(f"LLM Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/game/finish")
def finish_game(req: RatingRequest, db: Session = Depends(get_db)):
    session = db.query(GameSession).filter(GameSession.id == req.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session.status = "solved"
    session.rating = req.rating
    db.commit()
    return {"status": "success"}

@app.post("/api/game/giveup")
def give_up(req: RatingRequest, db: Session = Depends(get_db)):
    session = db.query(GameSession).filter(GameSession.id == req.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session.status = "given_up"
    db.commit()
    
    return {"truth": session.puzzle.truth}

# --- Pages ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/play/{puzzle_id}", response_class=HTMLResponse)
async def read_game(request: Request, puzzle_id: int):
    return templates.TemplateResponse("game.html", {"request": request, "puzzle_id": puzzle_id})
