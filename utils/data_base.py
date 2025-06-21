#data_base.py

import sqlite3
from typing import Dict, Any

# Database Functions
def create_database(db_path: str = 'research_analytics.db') -> sqlite3.Connection:
    """
    Create the database with the normalized schema, including sources.
    
    Args:
        db_path (str): Path to the database file
        
    Returns:
        sqlite3.Connection: Database connection object
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Make sure SQLite enforces foreign keys
    cursor.execute('PRAGMA foreign_keys = ON;')
    
    # Create tables
    cursor.executescript('''
        -- New table for sources
        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        );
        
        -- Core entities, now with source_id
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            journal_id INTEGER,
            source_id INTEGER,
            year INTEGER,
            abstract TEXT,
            FOREIGN KEY (journal_id) REFERENCES journals(id),
            FOREIGN KEY (source_id) REFERENCES sources(id)
        );
        
        CREATE TABLE IF NOT EXISTS authors (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        );
        
        CREATE TABLE IF NOT EXISTS journals (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        );
        
        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY,
            term TEXT NOT NULL UNIQUE
        );
        
        -- Relationship tables
        CREATE TABLE IF NOT EXISTS article_author (
            article_id INTEGER NOT NULL,
            author_id INTEGER NOT NULL,
            PRIMARY KEY (article_id, author_id),
            FOREIGN KEY (article_id) REFERENCES articles(id),
            FOREIGN KEY (author_id) REFERENCES authors(id)
        );
        
        CREATE TABLE IF NOT EXISTS article_keyword (
            article_id INTEGER NOT NULL,
            keyword_id INTEGER NOT NULL,
            PRIMARY KEY (article_id, keyword_id),
            FOREIGN KEY (article_id) REFERENCES articles(id),
            FOREIGN KEY (keyword_id) REFERENCES keywords(id)
        );
    ''')
    
    conn.commit()
    return conn


def get_statistics(db_path: str = 'research_analytics.db') -> Dict[str, Any]:
    """
    Get comprehensive statistics from the database.
    
    Args:
        db_path (str): Path to the database file
        
    Returns:
        Dict[str, Any]: Dictionary containing various statistics
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    stats = {}
    
    # Basic counts
    cursor.execute("SELECT COUNT(*) FROM articles")
    stats['total_articles'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM authors")
    stats['total_authors'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM journals")
    stats['total_journals'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM keywords")
    stats['total_keywords'] = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM sources")
    stats['total_sources'] = cursor.fetchone()[0]
    
    # Articles by source
    cursor.execute("""
        SELECT s.name, COUNT(a.id) as count
        FROM sources s
        LEFT JOIN articles a ON s.id = a.source_id
        GROUP BY s.name
        ORDER BY count DESC
    """)
    stats['articles_by_source'] = cursor.fetchall()
    
    # Articles by year
    cursor.execute("""
        SELECT year, COUNT(*) as count
        FROM articles
        WHERE year IS NOT NULL
        GROUP BY year
        ORDER BY year DESC
        LIMIT 10
    """)
    stats['articles_by_year'] = cursor.fetchall()
    
    # Top journals
    cursor.execute("""
        SELECT j.name, COUNT(a.id) as count
        FROM journals j
        LEFT JOIN articles a ON j.id = a.journal_id
        GROUP BY j.name
        ORDER BY count DESC
        LIMIT 10
    """)
    stats['top_journals'] = cursor.fetchall()
    
    # Top keywords
    cursor.execute("""
        SELECT k.term, COUNT(ak.article_id) as count
        FROM keywords k
        LEFT JOIN article_keyword ak ON k.id = ak.keyword_id
        GROUP BY k.term
        ORDER BY count DESC
        LIMIT 15
    """)
    stats['top_keywords'] = cursor.fetchall()
    
    # Most productive authors
    cursor.execute("""
        SELECT a.name, COUNT(aa.article_id) as count
        FROM authors a
        LEFT JOIN article_author aa ON a.id = aa.author_id
        GROUP BY a.name
        ORDER BY count DESC
        LIMIT 10
    """)
    stats['top_authors'] = cursor.fetchall()
    
    conn.close()
    return stats



def get_or_create_source(cursor, source_name):
    """
    Get existing source ID or create new source.
    
    """
    if not source_name:
        return None
    
    cursor.execute("SELECT id FROM sources WHERE name = ?", (source_name,))
    result = cursor.fetchone()
    
    if result:
        return result[0]
    else:
        cursor.execute("INSERT INTO sources (name) VALUES (?)", (source_name,))
        return cursor.lastrowid



def get_or_create_journal(cursor, journal_name):
    """Get journal ID or create new journal"""
    if not journal_name:
        return None
    
    cursor.execute("SELECT id FROM journals WHERE name = ?", (journal_name,))
    result = cursor.fetchone()
    
    if result:
        return result[0]
    else:
        cursor.execute("INSERT INTO journals (name) VALUES (?)", (journal_name,))
        return cursor.lastrowid

def get_or_create_author(cursor, author_name):
    """Get author ID or create new author"""
    if not author_name:
        return None
    
    cursor.execute("SELECT id FROM authors WHERE name = ?", (author_name,))
    result = cursor.fetchone()
    
    if result:
        return result[0]
    else:
        cursor.execute("INSERT INTO authors (name) VALUES (?)", (author_name,))
        return cursor.lastrowid

def get_or_create_keyword(cursor, keyword_term):
    """Get keyword ID or create new keyword"""
    if not keyword_term:
        return None
    
    cursor.execute("SELECT id FROM keywords WHERE term = ?", (keyword_term,))
    result = cursor.fetchone()
    
    if result:
        return result[0]
    else:
        cursor.execute("INSERT INTO keywords (term) VALUES (?)", (keyword_term,))
        return cursor.lastrowid




def display_statistics(db_path: str = 'research_analytics.db'):
    """
    Display comprehensive database statistics in a formatted way.
    """
    stats = get_statistics(db_path)
    
    print("=" * 60)
    print("           RESEARCH DATABASE STATISTICS")
    print("=" * 60)
    
    # Basic counts
    print("\n📊 OVERVIEW:")
    print(f"   Total Articles: {stats['total_articles']:,}")
    print(f"   Total Authors: {stats['total_authors']:,}")
    print(f"   Total Journals: {stats['total_journals']:,}")
    print(f"   Total Keywords: {stats['total_keywords']:,}")
    print(f"   Total Sources: {stats['total_sources']:,}")
    
    # Articles by source
    print("\n📚 ARTICLES BY SOURCE:")
    for source, count in stats['articles_by_source']:
        print(f"   {source}: {count:,} articles")
    
    # Articles by year
    print("\n📅 ARTICLES BY YEAR (Top 10):")
    for year, count in stats['articles_by_year']:
        print(f"   {year}: {count:,} articles")
    
    # Top journals
    print("\n📖 TOP JOURNALS (Top 10):")
    for i, (journal, count) in enumerate(stats['top_journals'], 1):
        journal_name = journal[:50] + "..." if len(journal) > 50 else journal
        print(f"   {i:2d}. {journal_name}: {count:,} articles")
    
    # Top keywords
    print("\n🏷️  TOP KEYWORDS (Top 15):")
    for i, (keyword, count) in enumerate(stats['top_keywords'], 1):
        print(f"   {i:2d}. {keyword}: {count:,} occurrences")
    
    # Top authors
    print("\n👥 MOST PRODUCTIVE AUTHORS (Top 10):")
    for i, (author, count) in enumerate(stats['top_authors'], 1):
        print(f"   {i:2d}. {author}: {count:,} articles")
    
    print("\n" + "=" * 60)

# Usage example
if __name__ == "__main__":
    # Call the function to display statistics
    display_statistics()
    
    # Or with a specific database path
    # display_statistics('path/to/your/database.db')