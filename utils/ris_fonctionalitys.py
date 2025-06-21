# ris_fonctionalitys.py
from typing import List
import os

def build_ideal_record(file_path: str) -> List[str]:
    """
    Build an ideal record by collecting the first occurrence of each unique tag with its content from the entire RIS file.
    
    Args:
        file_path (str): Path to the RIS file.
    
    Returns:
        List[str]: List of strings representing the ideal record with unique tags and their content.
    """
    ideal_record = []
    seen_tags = set()
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line_stripped = line.strip()
            if line_stripped and len(line_stripped) >= 5 and line_stripped[2:5] == "  -":
                tag = line_stripped[:2]
                if tag not in seen_tags:
                    seen_tags.add(tag)
                    ideal_record.append(line)
                    # Collect continuation lines
                    for next_line in f:
                        next_line_stripped = next_line.strip()
                        if next_line_stripped and len(next_line_stripped) >= 5 and next_line_stripped[2:5] == "  -":
                            break
                        else:
                            ideal_record.append(next_line)
    return ideal_record