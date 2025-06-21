#parser.py
from utils.data_base import create_database, get_or_create_journal, get_or_create_author, get_or_create_keyword, get_or_create_source
import re
from utils.ris_fonctionalitys import build_ideal_record
from utils.map_tags import generate_tag_mapping

def parse_ris_record(record_str : str, tag_mapping: dict[str, str]) -> dict[str, str |int | list[str] | None] :
    """
    Parse a single RIS record with improved multi-value handling and flexible tag mapping
    """
    # Get the actual tags from the mapping
    relevant_tags = tag_mapping.values()
    tags = {tag: [] for tag in relevant_tags}
    current_tag = None
    
    for line in record_str.splitlines():
        line = line.strip()
        if not line:
            continue
            
        # Process tag lines
        if len(line) >= 6 and line[2:5] == "  -":
            tag = line[:2]
            content = line[6:].strip()
            current_tag = tag if tag in relevant_tags else None
            if current_tag:
                tags[current_tag].append(content)
        # Handle continuation lines
        elif current_tag and tags[current_tag]:
            tags[current_tag][-1] += " " + line
    
    # Extract year from publication_year tag
    year = None
    pub_year_tag = tag_mapping.get('publication_year')
    if pub_year_tag and tags.get(pub_year_tag):
        match = re.search(r'\b\d{4}\b', tags[pub_year_tag][0])
        year = int(match.group()) if match else None
    
    # Build result using standardized keys
    result = {}
    
    # Title
    title_tag = tag_mapping.get('title')
    result['title'] = tags[title_tag][0] if title_tag and tags.get(title_tag) else None
    
    # Journal
    journal_tag = tag_mapping.get('journal_name')
    result['journal'] = tags[journal_tag][0] if journal_tag and tags.get(journal_tag) else None
    
    # Year
    result['year'] = year
    
    # Abstract
    abstract_tag = tag_mapping.get('abstract')
    result['abstract'] = ' '.join(tags[abstract_tag]) if abstract_tag and tags.get(abstract_tag) else None
    
    # Authors
    author_tag = tag_mapping.get('author')
    result['authors'] = [a.strip() for a in tags[author_tag]] if author_tag and tags.get(author_tag) else []
    
    # Keywords
    keywords_tag = tag_mapping.get('keywords')
    result['keywords'] = [k.strip() for k in tags[keywords_tag]] if keywords_tag and tags.get(keywords_tag) else []
    
    return result

def parse_ris_content(content, tag_mapping):
    """
    Parse RIS content string and extract all records
    """
    records = []
    current_record = []
    
    for line in content.splitlines():
        line = line.strip()
        
        # Check if this is the end of a record
        if line.startswith("ER") and ("  -" in line or line == "ER"):
            if current_record:
                record_str = '\n'.join(current_record)
                parsed_record = parse_ris_record(record_str, tag_mapping)
                
                # Only add records that have at least a title
                if parsed_record.get('title'):
                    records.append(parsed_record)
                
                current_record = []
        else:
            # Add line to current record (skip empty lines)
            if line:
                current_record.append(line)
    
    # Handle case where last record doesn't end with ER
    if current_record:
        record_str = '\n'.join(current_record)
        parsed_record = parse_ris_record(record_str, tag_mapping)
        if parsed_record.get('title'):
            records.append(parsed_record)
    
    return records

def store_record_in_database(cursor, record, source_name):
    """
    Store a single parsed record in the database with source information
    
    Args:
        cursor: Database cursor
        record: Parsed record dictionary
        source_name: Name of the data source (e.g., 'Scopus', 'ABI Inform', 'PubMed')
    
    Returns:
        int: Article ID of the inserted record
    """
    # Get or create source
    source_id = get_or_create_source(cursor, source_name)
    
    # Get or create journal
    journal_id = get_or_create_journal(cursor, record.get('journal'))
    
    # Insert article with source_id
    cursor.execute('''
        INSERT INTO articles (title, journal_id, source_id, year, abstract)
        VALUES (?, ?, ?, ?, ?)
    ''', (record['title'], journal_id, source_id, record.get('year'), record.get('abstract')))
    
    article_id = cursor.lastrowid
    
    # Insert authors and relationships
    for author_name in record.get('authors', []):
        if author_name:
            author_id = get_or_create_author(cursor, author_name)
            cursor.execute('''
                INSERT OR IGNORE INTO article_author (article_id, author_id)
                VALUES (?, ?)
            ''', (article_id, author_id))
    
    # Insert keywords and relationships
    for keyword_term in record.get('keywords', []):
        if keyword_term:
            keyword_id = get_or_create_keyword(cursor, keyword_term)
            cursor.execute('''
                INSERT OR IGNORE INTO article_keyword (article_id, keyword_id)
                VALUES (?, ?)
            ''', (article_id, keyword_id))
    
    return article_id

def process_ris_file(file_path, source_name, tag_mapping, db_path='research_analytics.db'):
    """
    Process an entire RIS file and store all records with the same source
    
    Args:
        file_path: Path to the RIS file
        source_name: Name of the data source for all records in this file
        tag_mapping: Dictionary mapping field names to RIS tags
        db_path: Path to the database file
    
    Returns:
        int: Number of records processed
    """
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Parse records
    records = parse_ris_content(content, tag_mapping)
    
    # Store in database
    conn = create_database(db_path)
    cursor = conn.cursor()
    
    processed_count = 0
    try:
        for record in records:
            store_record_in_database(cursor, record, source_name)
            processed_count += 1
        
        conn.commit()
        print(f"Successfully processed {processed_count} records from {source_name}")
        
    except Exception as e:
        conn.rollback()
        print(f"Error processing records: {e}")
        raise
    finally:
        conn.close()
    
    return processed_count

