from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime
import uuid

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True) # UUID
    nickname = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    game_sessions = relationship("GameSession", back_populates="user")

class Puzzle(Base):
    __tablename__ = "puzzles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    content = Column(Text) # Soup Surface (Question)
    truth = Column(Text)   # Soup Bottom (Answer)
    source_file = Column(String, unique=True)
    
    game_sessions = relationship("GameSession", back_populates="puzzle")

class GameSession(Base):
    __tablename__ = "game_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"))
    puzzle_id = Column(Integer, ForeignKey("puzzles.id"))
    status = Column(String, default="in_progress") # in_progress, solved, given_up
    # rating column removed
    rating_fun = Column(Integer, nullable=True)
    rating_logic = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="game_sessions")
    puzzle = relationship("Puzzle", back_populates="game_sessions")
    interactions = relationship("Interaction", back_populates="session")

class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("game_sessions.id"))
    role = Column(String) # user, ai, system
    content = Column(Text)
    is_legal = Column(Boolean, default=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    session = relationship("GameSession", back_populates="interactions")
