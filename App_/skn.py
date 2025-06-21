import streamlit as st

class AIScreener:
    """Handle AI screening operations with enhanced output structure"""
    
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
        """Screen a batch of articles with enhanced output structure"""
        if len(articles) > 3:
            articles = articles[:3]
        
        # Create prompt with article details
        articles_text = ""
        for i, article in enumerate(articles, 1):
            articles_text += f"""
Article {i}:
Title: {article['title']}
Abstract: {article['abstract']}
---
"""
        
        # Enhanced JSON structure with your required fields
        json_structure = {}
        for i in range(1, len(articles) + 1):
            json_structure[f"article_{i}"] = {
                "decision": "RELEVANT or NOT_RELEVANT",
                "confidence": "float between 0.0 and 1.0",
                "explanation": "detailed reasoning for the decision",
                "evidence": ["specific quotes or phrases from title/abstract that support the decision"]
            }
        
        prompt = f"""
You are screening research articles for systematic review relevance.

SCREENING CRITERIA: {criteria}

Analyze these {len(articles)} articles and provide structured output:

{articles_text}

For each article, provide:
1. DECISION: Either "RELEVANT" or "NOT_RELEVANT" based on the criteria
2. CONFIDENCE: A float between 0.0 and 1.0 representing your certainty in the decision
3. EXPLANATION: Clear reasoning explaining why the article meets or doesn't meet the criteria
4. EVIDENCE: Specific phrases or sentences from the title/abstract that support your decision

Guidelines:
- Be precise with confidence scores (0.9+ for very certain, 0.7-0.8 for moderately certain, 0.5-0.6 for uncertain)
- Extract exact phrases from the provided text for evidence
- Keep explanations concise but comprehensive
- Base decisions strictly on the provided criteria

Respond in the following JSON format:
{json.dumps(json_structure, indent=2)}
"""
        
        try:
            response = self.client.chat.completions.create(
                model="llama3-70b-8192",
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a systematic review expert. Analyze articles carefully and provide structured screening results in valid JSON format only."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2048,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Validate and clean the response
            return self._validate_screening_result(result, articles)
            
        except Exception as e:
            st.error(f"AI screening error: {e}")
            return None
    
    def _validate_screening_result(self, result, articles):
        """Validate and clean the screening result"""
        validated_result = {}
        
        for i, article in enumerate(articles, 1):
            article_key = f"article_{i}"
            
            if article_key in result:
                article_result = result[article_key]
                
                # Validate decision
                decision = str(article_result.get('decision', 'NOT_RELEVANT')).upper()
                if decision not in ['RELEVANT', 'NOT_RELEVANT']:
                    decision = 'NOT_RELEVANT'
                
                # Validate confidence
                try:
                    confidence = float(article_result.get('confidence', 0.5))
                    confidence = max(0.0, min(1.0, confidence))  # Clamp between 0 and 1
                except (ValueError, TypeError):
                    confidence = 0.5
                
                # Validate explanation
                explanation = str(article_result.get('explanation', 'No explanation provided'))
                
                # Validate evidence
                evidence = article_result.get('evidence', [])
                if not isinstance(evidence, list):
                    evidence = [str(evidence)] if evidence else []
                
                validated_result[article_key] = {
                    'decision': decision,
                    'confidence': confidence,
                    'explanation': explanation,
                    'evidence': evidence,
                    'title': article['title'],  # Include original title for reference
                    'abstract': article['abstract']  # Include original abstract for reference
                }
        
        return validated_result
    
    def format_screening_results(self, screening_results):
        """Format screening results for display"""
        if not screening_results:
            return "No screening results available."
        
        formatted_output = []
        
        for article_key, result in screening_results.items():
            formatted_output.append(f"""
**{article_key.replace('_', ' ').title()}:**
- **Decision:** {result['decision']}
- **Confidence:** {result['confidence']:.2f}
- **Explanation:** {result['explanation']}
- **Evidence:** {', '.join(result['evidence']) if result['evidence'] else 'No specific evidence extracted'}
- **Title:** {result['title'][:100]}{'...' if len(result['title']) > 100 else ''}
""")
        
        return '\n'.join(formatted_output)

# Example usage function
def example_usage():
    """Example of how to use the enhanced AIScreener"""
    
    # Sample articles
    sample_articles = [
        {
            'title': 'Machine Learning Applications in Healthcare Diagnosis',
            'abstract': 'This study explores the use of deep learning algorithms for automated medical diagnosis...'
        },
        {
            'title': 'Agricultural Pest Control Methods in Organic Farming',
            'abstract': 'An investigation into sustainable pest management strategies for organic agriculture...'
        }
    ]
    
    # Sample criteria
    criteria = "Studies related to artificial intelligence applications in healthcare"
    
    # Initialize screener
    screener = AIScreener()
    
    # Screen articles
    results = screener.screen_batch(sample_articles, criteria)
    
    # Format and display results
    if results:
        formatted_results = screener.format_screening_results(results)
        print(formatted_results)
        
        # Access individual components
        for article_key, result in results.items():
            print(f"\n{article_key}:")
            print(f"Decision: {result['decision']}")
            print(f"Confidence: {result['confidence']}")
            print(f"Explanation: {result['explanation']}")
            print(f"Evidence: {result['evidence']}")

if __name__ == '__name__':
    example_usage()