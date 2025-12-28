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
api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    print("WARNING: OPENROUTER_API_KEY is not set in environment variables.")
else:
    print(f"OPENROUTER_API_KEY loaded: {api_key[:4]}...{api_key[-4:]}")

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
)

MODEL_NAME = "google/gemini-2.5-flash-lite"

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
    rating_fun: Optional[int] = 0
    rating_logic: Optional[int] = 0

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
            "rating_fun": session.rating_fun,
            "rating_logic": session.rating_logic
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
你是一个海龟汤（情境推理游戏）的主持人。
汤面（题目）: {puzzle.content}
汤底（真相）: {puzzle.truth}

你的目标是回答用户的提问，帮助他们还原真相。
规则：
1. 只能回答“是”、“不是”或“没有关系”。
2. 如果用户的问题建立了错误的假设，你可以回答“不重要”或“不是”。
3. 如果用户请求提示，可以给出一点微小的线索，但绝不能直接泄露核心真相。
4. **输出格式**：每次回答必须以以下四个标记之一开头：
   - `[[SOLVED]]`：用户完全推导出了核心汤底和关键因果。请祝贺并简要总结。
   - `[[UNSOLVED]]`：用户在试图推导核心汤底和关键因果，但未解决谜题，请向用户说明情况，但不可揭露汤底。
   - `[[ANSWER]]`：用户是在提问（是非题）。你的回答内容**必须**是“是”、“不是”、“没有关系”、“不重要”这四个词中的一个。
   - `[[HINT]]`：用户明确请求提示，你需要给出一个微小的引导。
   5. **判定标准**：不要因为用户猜对了一点皮毛就判定 SOLVED，必须还原核心汤底。
6. 请保持简洁，用中文回答。
    """
    
    # Fetch recent history (limit context window if needed, here we take all)
    history_objs = db.query(Interaction).filter(Interaction.session_id == session.id).order_by(Interaction.timestamp).all()
    messages = [{"role": "system", "content": system_prompt}]
    for h in history_objs:
        # Convert internal role to API role
        role = "assistant" if h.role == "ai" else "user"
        # Filter out system generated truth messages from history context if any (though usually fine)
        messages.append({"role": role, "content": h.content})
        
    try:
        completion = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
        )
        ai_response_raw = completion.choices[0].message.content.strip()
        
        # --- Check Logic ---
        game_status = "in_progress"
        is_legal = False
        final_content = ai_response_raw
        
        # Parse Tag
        tag = None
        content_body = ai_response_raw
        for t in ["[[SOLVED]]", "[[ANSWER]]", "[[HINT]]", "[[UNSOLVED]]"]:
            if ai_response_raw.startswith(t):
                tag = t
                content_body = ai_response_raw.replace(t, "").strip()
                break
        
        if tag == "[[SOLVED]]":
            is_legal = True
            game_status = "solved"
            final_content = content_body
            if session.status != "given_up":
                session.status = "solved"
            final_content += f"\n\n**【真相】**\n{puzzle.truth}"
            
        elif tag == "[[ANSWER]]":
            # Strict Check: Must be one of the 4 keywords
            clean_body = content_body.replace("。", "").replace("！", "").strip()
            if clean_body in ["是", "不是", "没有关系", "不重要"]:
                is_legal = True
                final_content = content_body
                
        elif tag in ["[[HINT]]", "[[UNSOLVED]]"]:
            # Length Check: Max 100 chars (approx)
            if len(content_body) <= 100: # relaxed slightly to 100 for safety
                is_legal = True
                final_content = content_body
        
        else:
            # Fallback: strict check if no tag
            clean_body = ai_response_raw.replace("。", "").replace("！", "").strip()
            if clean_body in ["是", "不是", "没有关系", "不重要"]:
                is_legal = True
                final_content = ai_response_raw

        # Save AI Response
        ai_interaction = Interaction(
            session_id=session.id, 
            role="ai", 
            content=final_content,
            is_legal=is_legal
        )
        db.add(ai_interaction)
        db.commit()
        
        if not is_legal:
            return {"role": "ai", "content": "主持人保持沉默。（回答不符合规则）", "game_status": game_status}

        return {"role": "ai", "content": final_content, "game_status": game_status}
        
    except Exception as e:
        # Log error
        print(f"LLM Error: {e}")
        error_msg = str(e)
        if "401" in error_msg:
             return {"role": "ai", "content": "配置错误：无法连接到主持人 (401 Unauthorized)。请检查服务器 API Key。"}
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/game/finish")
def finish_game(req: RatingRequest, db: Session = Depends(get_db)):
    session = db.query(GameSession).filter(GameSession.id == req.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session.status == "in_progress":
        session.status = "solved"
        
    if req.rating_fun:
        session.rating_fun = req.rating_fun
    if req.rating_logic:
        session.rating_logic = req.rating_logic
        
    db.commit()
    return {"status": "success"}

@app.post("/api/game/giveup")
def give_up(req: RatingRequest, db: Session = Depends(get_db)):
    session = db.query(GameSession).filter(GameSession.id == req.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session.status = "given_up"
    
    # Save Truth to Chat History
    truth_content = f"**【真相】**\n{session.puzzle.truth}"
    system_interaction = Interaction(
        session_id=session.id,
        role="ai", # Display as AI message
        content=truth_content,
        is_legal=True
    )
    db.add(system_interaction)
    db.commit()
    
    return {"truth": session.puzzle.truth}

# --- Pages ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/play/{puzzle_id}", response_class=HTMLResponse)
async def read_game(request: Request, puzzle_id: int):
    return templates.TemplateResponse("game.html", {"request": request, "puzzle_id": puzzle_id})
