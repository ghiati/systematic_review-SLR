# main.py - Integrated Research Analytics Application
import streamlit as st
from datetime import datetime
import pandas as pd

# Import functions from your existing files
from App_.app import (
    process_uploaded_file, 
    display_duplicates_analysis, 
    display_partial_duplicates_analysis,
    display_enhanced_statistics,
    create_excel_download_button
)

# Import screening classes from screening.py
from App_.screening import DatabaseManager, AIScreener, initialize_session_state

# Import database utilities
from utils.data_base import create_database


def render_ai_screening_tab():
    """Render the AI Screening tab with all functionality from screening.py"""
    st.header("🤖 AI-Powered Article Screening")
    st.caption("Systematic review screening tool with AI assistance")
    
    # Initialize session state for screening
    initialize_session_state()
    
    # Initialize managers
    db = DatabaseManager()
    ai_screener = AIScreener()
    
    # Sidebar stats (integrated into main content for tab layout)
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.subheader("📊 Screening Statistics")
    
    with col2:
        total_articles = db.get_total_count()
        st.metric("Total Articles", total_articles)
    
    with col3:
        if st.button("🔄 New Screening Session"):
            for key in ['screening_results', 'screening_completed', 'final_decisions']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    
    # Additional stats if screening completed
    if st.session_state.screening_completed:
        st.divider()
        results_df = pd.DataFrame(st.session_state.screening_results)
        included = len(results_df[results_df['ai_decision'] == 'INCLUDE'])
        excluded = len(results_df[results_df['ai_decision'] == 'EXCLUDE'])
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("AI Recommended Include", included)
        with col2:
            st.metric("AI Recommended Exclude", excluded)
        
        # Final decisions count
        final_include = sum(1 for decision in st.session_state.final_decisions.values() if decision == 'INCLUDE')
        final_exclude = sum(1 for decision in st.session_state.final_decisions.values() if decision == 'EXCLUDE')
        
        with col3:
            st.metric("Your Decision: Include", final_include)
        with col4:
            st.metric("Your Decision: Exclude", final_exclude)
    
    st.divider()
    
    # Get articles for screening
    articles_df = db.get_articles()
    if articles_df.empty:
        st.warning("⚠️ No articles found in database!")
        st.info("Please upload some RIS files first using the main application tabs.")
        return
    
    st.success(f"✅ Loaded {len(articles_df)} articles for screening")
    
    # Criteria input
    st.subheader("📋 Define Screening Criteria")
    criteria = st.text_area(
        "Enter your inclusion/exclusion criteria:",
        placeholder="Example: Include studies about machine learning in healthcare published after 2020. Exclude review articles and case studies.",
        height=120,
        key="criteria_input",
        help="Be specific about what you want to include or exclude. The AI will use these criteria to make recommendations."
    )
    
    # Start AI screening
    if criteria and not st.session_state.screening_completed:
        if st.button("🚀 Start AI Screening", type="primary"):
            with st.spinner("🤖 AI is analyzing articles based on your criteria..."):
                results = []
                
                # Process in batches of 3
                for i in range(0, len(articles_df), 3):
                    batch = articles_df.iloc[i:i+3].to_dict('records')
                    batch_results = ai_screener.screen_batch(batch, criteria)
                    
                    if batch_results:
                        for j, article in enumerate(batch):
                            key = f"article_{j+1}"
                            if key in batch_results:
                                results.append({
                                    'id': article['id'],
                                    'title': article['title'],
                                    'abstract': article['abstract'],
                                    'ai_decision': batch_results[key]['decision'],
                                    'ai_explanation': batch_results[key]['explanation']
                                })
                
                st.session_state.screening_results = results
                st.session_state.screening_completed = True
                
                # Initialize final decisions with AI recommendations
                for result in results:
                    st.session_state.final_decisions[result['id']] = result['ai_decision']
                
                st.rerun()
    
    # Display screening results
    if st.session_state.screening_completed:
        st.divider()
        st.header("📋 Review AI Recommendations")
        st.write("Review each article and make your final decision:")
        
        # Display each article
        for i, result in enumerate(st.session_state.screening_results):
            article_id = result['id']
            
            # Create a container for each article
            with st.container():
                st.divider()
                
                # Article header with AI recommendation
                ai_icon = "🟢" if result['ai_decision'] == 'INCLUDE' else "🔴"
                st.subheader(f"{ai_icon} Article {i+1}")
                
                # Two columns: content and decision
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    # Title
                    st.write(f"**Title:** {result['title']}")
                    
                    # Abstract
                    st.write("**Abstract:**")
                    st.write(result['abstract'])
                    
                    # AI recommendation
                    st.write(f"**🤖 AI Recommendation:** {result['ai_decision']}")
                    st.write(f"**🤖 AI Explanation:** {result['ai_explanation']}")
                
                with col2:
                    # Final decision selector
                    current_decision = st.session_state.final_decisions.get(article_id, result['ai_decision'])
                    
                    final_decision = st.selectbox(
                        "Your Final Decision:",
                        ["INCLUDE", "EXCLUDE"],
                        index=0 if current_decision == 'INCLUDE' else 1,
                        key=f"decision_{article_id}",
                        help="INCLUDE = Keep in database\nEXCLUDE = Remove from database"
                    )
                    
                    # Update session state
                    st.session_state.final_decisions[article_id] = final_decision
                    
                    # Visual indicator
                    if final_decision == 'INCLUDE':
                        st.success("✅ Will Keep")
                    else:
                        st.error("❌ Will Remove")
        
        # Confirmation section
        st.divider()
        st.header("🔒 Confirm Database Changes")
        
        # Summary of decisions
        to_keep = [aid for aid, decision in st.session_state.final_decisions.items() if decision == 'INCLUDE']
        to_remove = [aid for aid, decision in st.session_state.final_decisions.items() if decision == 'EXCLUDE']
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Articles to Keep", len(to_keep))
        with col2:
            st.metric("Articles to Remove", len(to_remove))
        with col3:
            new_total = db.get_total_count() - len(to_remove)
            st.metric("New Database Total", new_total)
        
        if len(to_remove) > 0:
            st.warning(f"⚠️ You are about to remove {len(to_remove)} articles from the database!")
            
            # Show articles to be removed
            with st.expander("👀 Preview Articles to Remove"):
                for result in st.session_state.screening_results:
                    if result['id'] in to_remove:
                        st.write(f"• {result['title']}")
            
            # Confirmation input
            confirm_text = st.text_input(
                f"Type 'CONFIRM {len(to_remove)}' to proceed with removing {len(to_remove)} articles:"
            )
            
            if confirm_text == f"CONFIRM {len(to_remove)}":
                if st.button("🗑️ REMOVE ARTICLES FROM DATABASE", type="primary"):
                    with st.spinner("Updating database..."):
                        removed_count = db.remove_articles(to_remove)
                        
                        if removed_count > 0:
                            # Log the session
                            session_data = {
                                'total': len(st.session_state.screening_results),
                                'ai_included': len([r for r in st.session_state.screening_results if r['ai_decision'] == 'INCLUDE']),
                                'ai_excluded': len([r for r in st.session_state.screening_results if r['ai_decision'] == 'EXCLUDE']),
                                'final_kept': len(to_keep),
                                'final_removed': removed_count,
                                'criteria': criteria
                            }
                            db.log_session(session_data)
                            
                            st.success(f"✅ Successfully removed {removed_count} articles from the database!")
                            st.balloons()
                            
                            # Reset for new session
                            for key in ['screening_results', 'screening_completed', 'final_decisions']:
                                if key in st.session_state:
                                    del st.session_state[key]
                            
                            st.rerun()
        else:
            st.success("🎉 No articles will be removed from the database!")
            if st.button("✅ Complete Screening Session"):
                # Log the session
                session_data = {
                    'total': len(st.session_state.screening_results),
                    'ai_included': len([r for r in st.session_state.screening_results if r['ai_decision'] == 'INCLUDE']),
                    'ai_excluded': len([r for r in st.session_state.screening_results if r['ai_decision'] == 'EXCLUDE']),
                    'final_kept': len(to_keep),
                    'final_removed': 0,
                    'criteria': criteria
                }
                db.log_session(session_data)
                
                st.success("✅ Screening session completed successfully!")
                
                # Reset for new session
                for key in ['screening_results', 'screening_completed', 'final_decisions']:
                    if key in st.session_state:
                        del st.session_state[key]
                
                st.rerun()


def safe_process_uploaded_file(uploaded_file, source_name):
    """Safely process uploaded file with proper error handling"""
    try:
        # Call the original function
        results = process_uploaded_file(uploaded_file, source_name)
        return results, None
    except TypeError as e:
        if "unhashable type: 'list'" in str(e):
            # This specific error usually means there's an issue with tag mapping
            error_msg = """
            **Tag Mapping Error**: There appears to be an issue with the RIS tag mapping configuration.
            
            **Possible Solutions:**
            1. Check that your RIS file format is correct
            2. Verify the tag mapping in your parser configuration
            3. Try with a different RIS file to test
            
            **Technical Details:** The parser encountered list objects where string keys were expected.
            """
            return None, error_msg
        else:
            return None, f"Type Error: {str(e)}"
    except Exception as e:
        return None, f"Processing Error: {str(e)}"


def main():
    """Main application function"""
    # Initialize database
    create_database('research_analytics.db')
    
    # Set page config
    st.set_page_config(
        page_title="Research Analytics - Complete System",
        page_icon="📚",
        layout="wide"
    )
    
    st.title("📚 Research Analytics - Complete System")
    st.markdown("Upload, process, analyze, and screen research articles with AI assistance")
    
    # Sidebar for file upload (same as app.py)
    with st.sidebar:
        st.header("📤 Upload RIS File")
        
        uploaded_file = st.file_uploader(
            "Choose a RIS file",
            type=['ris'],
            help="Upload your RIS bibliography file"
        )
        
        source_name = st.text_input(
            "Source Name *",
            placeholder="e.g., Scopus, PubMed, Web of Science",
            help="Enter the name of the database/source (required)"
        )
        
        process_button = st.button(
            "🚀 Process File",
            disabled=(uploaded_file is None or not source_name.strip()),
            use_container_width=True
        )
    
    # Process file if button clicked with improved error handling
    results = None
    if process_button and uploaded_file and source_name.strip():
        with st.spinner("Processing RIS file..."):
            results, error_msg = safe_process_uploaded_file(uploaded_file, source_name.strip())
            
            if results:
                st.success("✅ File processed successfully!")
            
                # Processing summary
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("📄 Total Records", results['total_records'])
                with col2:
                    st.metric("✅ Stored (Unique)", results['unique_stored'])
                with col3:
                    st.metric("🚫 Full Duplicates", results['full_duplicates_found'])
                with col4:
                    st.metric("🤔 Partial Matches", results['partial_duplicates_found'])
            else:
                st.error("❌ Error processing file:")
                st.markdown(error_msg)
                
                # Show debug information
                with st.expander("🔍 Debug Information"):
                    st.write("**File Details:**")
                    st.write(f"- File name: {uploaded_file.name}")
                    st.write(f"- File size: {uploaded_file.size} bytes")
                    st.write(f"- Source name: {source_name}")
                    
                    # Show first few lines of the file
                    try:
                        uploaded_file.seek(0)
                        content = uploaded_file.read().decode('utf-8')
                        lines = content.split('\n')[:10]
                        st.write("**First 10 lines of file:**")
                        st.code('\n'.join(lines))
                        uploaded_file.seek(0)  # Reset file pointer
                    except Exception as debug_e:
                        st.write(f"Could not read file for debug: {debug_e}")
    
    # Main tabs - now with 6 tabs including AI Screening
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🔍 Full Duplicates", 
        "🤔 Partial Matches", 
        "📊 Database Statistics", 
        "🏷️ Tag Mapping", 
        "🔬 AI Screening"
    ])
    
    # Tab 1: Full Duplicates (same as app.py)
    with tab1:
        st.header("Full Duplicate Analysis")
        if results and 'full_duplicates_info' in results:
            display_duplicates_analysis(results['full_duplicates_info'])
        else:
            st.info("No duplicate analysis available. Process a file to see duplicate information.")
    
    # Tab 2: Partial Matches (same as app.py)
    with tab2:
        st.header("Partial Match Analysis - User Review Required")
        if results and 'partial_duplicates_info' in results:
            display_partial_duplicates_analysis(results['partial_duplicates_info'])
        else:
            st.info("No partial match analysis available. Process a file to see partial duplicate information.")
    
    # Tab 3: Database Statistics (same as app.py)
    with tab3:
        st.header("Database Statistics")
        try:
            display_enhanced_statistics()
        except Exception as e:
            st.info("No database found. Upload your first RIS file to get started!")
    
    # Tab 4: Tag Mapping (same as app.py)
    with tab4:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.header("RIS Tag Mapping Used")
        with col2:
            if results and 'tag_mapping' in results:
                tag_mapping_df = pd.DataFrame(list(results['tag_mapping'].items()), 
                                            columns=['RIS_Tag', 'Field_Name'])
                create_excel_download_button(
                    tag_mapping_df,
                    "tag_mapping",
                    "Export Tag Mapping",
                    "export_tag_mapping"
                )   
        
        if results and 'tag_mapping' in results:
            st.json(results['tag_mapping'])
        else:
            st.info("No tag mapping available. Process a file to see the RIS tag mapping used.")

    # Tab 5: AI Screening (NEW - integrated from screening.py)
    with tab5:
        render_ai_screening_tab()


if __name__ == "__main__":
    main()