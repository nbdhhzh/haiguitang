import os
import re
from sqlalchemy.orm import Session
from .database import SessionLocal, engine, Base
from .models import Puzzle

# Initialize Database
Base.metadata.create_all(bind=engine)

def parse_markdown_puzzle(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Simple regex to extract sections. 
    # Assumes format: 
    # ### 汤面 (Soup Surface) ... ### 汤底 (Soup Bottom) ...
    # Adjusting regex to be flexible with headers
    
    soup_surface_match = re.search(r'###\s*汤面\s*\n(.*?)(?=###|$)', content, re.DOTALL)
    soup_bottom_match = re.search(r'###\s*汤底\s*\n(.*?)(?=###|$)', content, re.DOTALL)
    
    if not soup_surface_match:
        # Fallback or skip
        print(f"Skipping {file_path}: No '汤面' found.")
        return None
        
    soup_surface = soup_surface_match.group(1).strip()
    soup_bottom = soup_bottom_match.group(1).strip() if soup_bottom_match else "无答案"
    
    # Title is filename without extension
    title = os.path.splitext(os.path.basename(file_path))[0]
    
    return {
        "title": title,
        "content": soup_surface,
        "truth": soup_bottom,
        "source_file": os.path.basename(file_path)
    }

def ingest_puzzles(puzzles_dir):
    db: Session = SessionLocal()
    try:
        if not os.path.exists(puzzles_dir):
            print(f"Directory not found: {puzzles_dir}")
            return

        for filename in os.listdir(puzzles_dir):
            if filename.endswith(".md"):
                file_path = os.path.join(puzzles_dir, filename)
                data = parse_markdown_puzzle(file_path)
                if data:
                    # Check if exists
                    existing = db.query(Puzzle).filter(Puzzle.source_file == data['source_file']).first()
                    if existing:
                        existing.title = data['title']
                        existing.content = data['content']
                        existing.truth = data['truth']
                        print(f"Updated: {data['title']}")
                    else:
                        new_puzzle = Puzzle(**data)
                        db.add(new_puzzle)
                        print(f"Added: {data['title']}")
        db.commit()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    # Adjust path relative to where script is run (usually from root or server dir)
    # If run from 'server' dir, ../static/puzzles. If run from root, static/puzzles
    # We will assume this script is run as a module or we handle paths absolutely.
    # Current working dir is D:\haiguitang
    PUZZLES_DIR = os.path.join("..", "static", "puzzles") 
    
    # If we run this script directly inside server/
    if not os.path.exists(PUZZLES_DIR):
        PUZZLES_DIR = os.path.join("static", "puzzles") # If run from root

    if not os.path.exists(PUZZLES_DIR):
         # Try absolute path based on known structure
         PUZZLES_DIR = r"D:\haiguitang\static\puzzles"

    print(f"Ingesting from {PUZZLES_DIR}")
    ingest_puzzles(PUZZLES_DIR)
