# screening.py

import sqlite3
import pandas as pd
import streamlit as st
from datetime import datetime
import json
import os
from dotenv import load_dotenv
from groq import Groq

# Load environment variables
load_dotenv()

class DatabaseManager:
    """Handle all database operations"""
    
    def __init__(self, db_path='research_analytics.db'):
        self.db_path = db_path
          
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_articles(self, limit=7):
        """Fetch articles from database"""
        try:
            with self.get_connection() as conn:
                query = "SELECT id, title, abstract FROM articles LIMIT ?;"
                return pd.read_sql_query(query, conn, params=[limit])
        except Exception as e:
            st.error(f"Error fetching articles: {e}")
            return pd.DataFrame()
    
    def get_total_count(self):
        """Get total article count"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM articles")
                return cursor.fetchone()[0]
        except Exception as e:
            st.error(f"Error getting count: {e}")
            return 0
    
    def remove_articles(self, article_ids):
        """Remove articles by IDs"""
        if not article_ids:
            return 0
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                placeholders = ','.join(['?' for _ in article_ids])
                
                # Remove from related tables first
                cursor.execute(f"DELETE FROM article_author WHERE article_id IN ({placeholders})", article_ids)
                cursor.execute(f"DELETE FROM article_keyword WHERE article_id IN ({placeholders})", article_ids)
                cursor.execute(f"DELETE FROM articles WHERE id IN ({placeholders})", article_ids)
                
                removed_count = cursor.rowcount
                conn.commit()
                return removed_count
        except Exception as e:
            st.error(f"Error removing articles: {e}")
            return 0
    
    def log_session(self, session_data):
        """Log screening session"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS screening_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_date TEXT,
                        total_articles INTEGER,
                        ai_included INTEGER,
                        ai_excluded INTEGER,
                        final_kept INTEGER,
                        final_removed INTEGER,
                        criteria TEXT
                    )
                ''')
                
                cursor.execute('''
                    INSERT INTO screening_log 
                    (session_date, total_articles, ai_included, ai_excluded, final_kept, final_removed, criteria)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    session_data['total'],
                    session_data['ai_included'],
                    session_data['ai_excluded'],
                    session_data['final_kept'],
                    session_data['final_removed'],
                    session_data['criteria']
                ))
                conn.commit()
        except Exception as e:
            st.error(f"Error logging session: {e}")


class AIScreener:
    """Handle AI screening operations"""
    
    def __init__(self):
        self.client = self._get_client()
    
    @st.cache_resource
    def _get_client(_self):
        """Initialize Groq client"""
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            st.error("GROQ_API_KEY not found!")
            st.stop()
        return Groq(api_key=api_key)
    
    def screen_batch(self, articles, criteria):
        """Screen a batch of articles"""
        if len(articles) > 3:
            articles = articles[:3]
        
        # Create prompt
        articles_text = ""
        for i, article in enumerate(articles, 1):
            articles_text += f"""
Article {i}:
Title: {article['title']}
Abstract: {article['abstract']}
---
"""
        
        # JSON structure
        json_structure = {}
        for i in range(1, len(articles) + 1):
            json_structure[f"article_{i}"] = {
                "decision": "INCLUDE or EXCLUDE",
                "explanation": "Brief explanation"
            }
        
        prompt = f"""
You are screening research articles for relevance.

CRITERIA: {criteria}

Analyze these {len(articles)} articles:
{articles_text}

Respond in JSON format:
{json.dumps(json_structure, indent=2)}
"""
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-r1-distill-llama-70b",
                messages=[
                    {"role": "system", "content": "You are a systematic review expert. Output valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2048,
                response_format={"type": "json_object"}
            )
            
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            st.error(f"AI screening error: {e}")
            return None


def initialize_session_state():
    """Initialize session state variables"""
    defaults = {
        'screening_results': [],
        'screening_completed': False,
        'final_decisions': {}
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

