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
4. **关键判定标准**：只有当用户**完全推导出了核心真相（汤底）的所有关键要素**（包括但不限于：关键人物的动机、具体手法、事件的因果逻辑等）时，才可以使用 `[[SOLVED]]` 标记。
   - 如果用户只猜对了一部分，或者只是接近真相但缺乏关键细节，请继续回答“是”或“不是”，引导他们补充完整。
   - **绝对不要**在用户仅猜出大概结果而未解释原因时判定胜利。
   - 判定胜利时，请以确切的标记 `[[SOLVED]]` 开头，然后祝贺他们，并简要总结为什么他们是正确的。
5. 请保持简洁，用中文回答。
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
        
        # --- Solved Check ---
        game_status = "in_progress"
        if "[[SOLVED]]" in ai_response:
            game_status = "solved"
            ai_response = ai_response.replace("[[SOLVED]]", "").strip()
            # Update DB (only if not already given up)
            if session.status != "given_up":
                session.status = "solved"
            
        # --- Safety/Legality Check ---
        is_legal = True
        
        # 1. Length Check
        if len(ai_response) > 800: 
             is_legal = False 
             
        # 2. Keyword Check (Simple safeguard)
        forbidden_terms = ["真相是", "答案是", "汤底是"]
        # Allow specific terms if solved
        if game_status != "solved" and any(term in ai_response for term in forbidden_terms):
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
            return {"role": "ai", "content": "主持人保持沉默。（回答因安全原因被过滤）", "game_status": game_status}

        return {"role": "ai", "content": ai_response, "game_status": game_status}
        
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
    
    # If not already finished, mark as solved (assuming this is called when solved or rating after give up)
    # Actually, logic:
    # 1. If solved naturally, status is already 'solved'.
    # 2. If give up, status is 'given_up'.
    # 3. If calling finish, it's mostly to save rating.
    
    # We respect the 'given_up' status if it exists.
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
    db.commit()
    
    return {"truth": session.puzzle.truth}

# --- Pages ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/play/{puzzle_id}", response_class=HTMLResponse)
async def read_game(request: Request, puzzle_id: int):
    return templates.TemplateResponse("game.html", {"request": request, "puzzle_id": puzzle_id})
