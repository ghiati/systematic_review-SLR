#map_tags.py
import os
from dotenv import load_dotenv
from groq import Groq  
from utils.ris_fonctionalitys import build_ideal_record
load_dotenv()

api_key = os.getenv("GROQ_API_KEY")


# Load environment variables
# api_key = "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"

if not api_key:
    raise RuntimeError("GROQ_API_KEY not found in environment.")
client = Groq(api_key=api_key)

def generate_tag_mapping(ris_record: list) -> dict:
    """
    Identify RIS tags corresponding to six predefined fields by analyzing only content patterns.
    Returns a dictionary mapping field names to RIS tags, with null values for missing fields.
    """
    try:
        prompt = f"""
You are an expert in bibliographic data analysis. Analyze the following RIS record and map each RIS tag to one of six fields based ONLY on the CONTENT of each tag's line.

The six fields and their content patterns are:
1. title: Short phrases/sentences (article titles)
2. author: Personal names (format: "Lastname, Firstname")
3. journal_name: Periodical titles (often include "Journal", "Proceedings", etc.)
4. publication_year: 4-digit years (e.g., 2023 not (feb,2020 and 12/2010)) 
5. keywords: Short descriptive terms/phrases
6. abstract: Paragraph-length descriptive text

RIS Record to analyze:
{ris_record}

Instructions:
- Examine the CONTENT after each tag
- Identify which tag corresponds to each field based on content patterns
- If a field has NO corresponding tag in the record, return null for that field
- For fields that DO have corresponding tags, return the actual RIS tag
- Return ONLY JSON with this structure:

Return only the JSON object, no additional text.
"""

        response = client.chat.completions.create(
            model="deepseek-r1-distill-llama-70b",  # Updated to Groq's available model
            messages=[
                {
                    "role": "system",
                    "content": "You are a bibliographic expert. Analyze line content and output ONLY JSON with six field-tag mappings."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=1024,
            top_p=0.9,
            response_format={"type": "json_object"}
        )

        # Debugging output
        #print("Raw API response:", response.choices[0].message.content)
        
        return response.choices[0].message.content

    except Exception as e:
        print(f"Error: {str(e)}")
        return None

# Example usage
if __name__ == "__main__":
    # Define your tags mapping
    first_record = (build_ideal_record(file_path = "/Users/mustaphaghiati/systematic_review/ProQuestDocuments-2025-06-06.ris"))
    print("first record :", first_record)
    tags_map = generate_tag_mapping(first_record)
    print(tags_map)