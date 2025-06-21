#app.py
import streamlit as st
import sqlite3
import json
import tempfile
import os
from io import BytesIO
from datetime import datetime
from typing import Dict, List, Tuple
import pandas as pd

from utils.data_base import create_database, get_statistics, display_statistics
from utils.parser import parse_ris_content, store_record_in_database
from utils.ris_fonctionalitys import build_ideal_record
from utils.map_tags import generate_tag_mapping


def create_excel_download_button(data, filename_prefix, button_label, key):
    """Create a download button for Excel export"""
    try:
        buffer = BytesIO()
        
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            if isinstance(data, dict):
                for sheet_name, df in data.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
            else:
                data.to_excel(writer, sheet_name='Data', index=False)
        
        excel_data = buffer.getvalue()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename_prefix}_{timestamp}.xlsx"
        
        st.download_button(
            label=f"📥 {button_label}",
            data=excel_data,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=key,
            use_container_width=True
        )
    except Exception as e:
        st.error(f"Error creating Excel file: {str(e)}")

# Add this function to get duplicates data for export
def get_duplicates_for_export(duplicates_info):
    """Convert duplicates info to DataFrame for export"""
    if not duplicates_info:
        return pd.DataFrame()
    
    export_data = []
    for i, dup in enumerate(duplicates_info):
        row = {
            'Duplicate_ID': i + 1,
            'New_Record_Title': dup['new_record'].get('title', 'N/A'),
            'New_Record_Source': dup['source_name'],
            'New_Record_Year': dup['new_record'].get('year', 'N/A'),
            'New_Record_Abstract': dup['new_record'].get('abstract', 'N/A'),
            'Duplicate_Type': ', '.join(dup['duplicate_type']),
            'Existing_Records_Count': len(dup['title_duplicates']) + len(dup['abstract_duplicates'])
        }
        
        # Add details of existing duplicates
        all_existing = []
        for title_dup in dup['title_duplicates']:
            all_existing.append(f"Title Match: {title_dup[0]} ({title_dup[1]}, {title_dup[2]})")
        for abs_dup in dup['abstract_duplicates']:
            all_existing.append(f"Abstract Match: {abs_dup[0]} ({abs_dup[1]}, {abs_dup[2]})")
        
        row['Existing_Duplicates'] = '; '.join(all_existing)
        export_data.append(row)
    
    return pd.DataFrame(export_data)

# Add this function to get statistics data for export
def get_statistics_for_export(db_path='research_analytics.db'):
    """Get all statistics data formatted for Excel export"""
    stats = get_statistics(db_path)
    
    export_data = {}
    
    # Basic overview
    overview_data = {
        'Metric': ['Total Articles', 'Total Authors', 'Total Journals', 'Total Keywords', 'Total Sources'],
        'Count': [stats['total_articles'], stats['total_authors'], stats['total_journals'], 
                 stats['total_keywords'], stats['total_sources']]
    }
    export_data['Overview'] = pd.DataFrame(overview_data)
    
    # Articles by source
    if stats['articles_by_source']:
        export_data['Articles_by_Source'] = pd.DataFrame(stats['articles_by_source'], columns=['Source', 'Count'])
    
    # Articles by year
    if stats['articles_by_year']:
        export_data['Articles_by_Year'] = pd.DataFrame(stats['articles_by_year'], columns=['Year', 'Count'])
    
    # Top journals
    if stats['top_journals']:
        export_data['Top_Journals'] = pd.DataFrame(stats['top_journals'], columns=['Journal', 'Articles'])
    
    # Top authors
    if stats['top_authors']:
        export_data['Top_Authors'] = pd.DataFrame(stats['top_authors'], columns=['Author', 'Articles'])
    
    # Top keywords
    if stats['top_keywords']:
        export_data['Top_Keywords'] = pd.DataFrame(stats['top_keywords'], columns=['Keyword', 'Occurrences'])
    
    return export_data

def check_duplicates(db_path: str, new_records: List[Dict], source_name: str) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Check for duplicates based on title and abstract
    
    Returns:
        Tuple of (unique_records, full_duplicates, partial_duplicates)
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    unique_records = []
    full_duplicates = []
    partial_duplicates = []
    
    for record in new_records:
        title = record.get('title', '').strip().lower()
        abstract = record.get('abstract', '').strip().lower() if record.get('abstract') else ''
        
        # Check for title duplicates
        cursor.execute("""
            SELECT a.title, s.name as source, a.year, a.id, a.abstract
            FROM articles a
            LEFT JOIN sources s ON a.source_id = s.id
            WHERE LOWER(TRIM(a.title)) = ?
        """, (title,))
        
        title_duplicates = cursor.fetchall()
        
        # Check for abstract duplicates if abstract exists
        abstract_duplicates = []
        if abstract:
            cursor.execute("""
                SELECT a.title, s.name as source, a.year, a.id, a.abstract
                FROM articles a
                LEFT JOIN sources s ON a.source_id = s.id
                WHERE LOWER(TRIM(a.abstract)) = ? AND a.abstract IS NOT NULL
            """, (abstract,))
            abstract_duplicates = cursor.fetchall()
        
        if title_duplicates or abstract_duplicates:
            # This is a duplicate
            duplicate_info = {
                'new_record': record,
                'source_name': source_name,
                'title_duplicates': title_duplicates,
                'abstract_duplicates': abstract_duplicates,
                'duplicate_type': []
            }
            
            if title_duplicates:
                duplicate_info['duplicate_type'].append('title')
            if abstract_duplicates:
                duplicate_info['duplicate_type'].append('abstract')
            
            # Check if it's a full duplicate (both title AND abstract match) or partial
            has_both_title_and_abstract_match = False
            
            if title_duplicates and abstract_duplicates:
                # Check if there's any record that matches BOTH title and abstract
                title_ids = {dup[3] for dup in title_duplicates}  # ID is at index 3
                abstract_ids = {dup[3] for dup in abstract_duplicates}
                common_ids = title_ids.intersection(abstract_ids)
                has_both_title_and_abstract_match = len(common_ids) > 0
            
            if has_both_title_and_abstract_match:
                full_duplicates.append(duplicate_info)
            else:
                # This is a partial duplicate - user needs to decide
                partial_duplicates.append(duplicate_info)
        else:
            # This is unique
            unique_records.append(record)
    
    conn.close()
    return unique_records, full_duplicates, partial_duplicates

def process_uploaded_file(uploaded_file, source_name: str, db_path: str = 'research_analytics.db'):
    """
    Process uploaded RIS file and return processing results
    """
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.ris', delete=False) as tmp_file:
        content = uploaded_file.getvalue().decode('utf-8')
        tmp_file.write(content)
        tmp_file_path = tmp_file.name
    
    try:
        # Generate tag mapping
        tag_mapping_str = generate_tag_mapping(build_ideal_record(tmp_file_path))
        tag_mapping = json.loads(tag_mapping_str)
        
        # Parse RIS content
        records = parse_ris_content(content, tag_mapping)
        
        # Check for duplicates (now returns 3 categories)
        unique_records, full_duplicates, partial_duplicates = check_duplicates(db_path, records, source_name)
        
        # Store unique records in database
        conn = create_database(db_path)
        cursor = conn.cursor()
        
        stored_count = 0
        try:
            for record in unique_records:
                store_record_in_database(cursor, record, source_name)
                stored_count += 1
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
        
        return {
            'total_records': len(records),
            'unique_stored': stored_count,
            'full_duplicates_found': len(full_duplicates),
            'partial_duplicates_found': len(partial_duplicates),
            'full_duplicates_info': full_duplicates,
            'partial_duplicates_info': partial_duplicates,
            'tag_mapping': tag_mapping
        }
        
    finally:
        # Clean up temporary file
        os.unlink(tmp_file_path)


def display_partial_duplicates_analysis(partial_duplicates_info: List[Dict]):
    """
    Display partial duplicate analysis that requires user review
    """
    if not partial_duplicates_info:
        st.success("🎉 No partial matches found!")
        return
    
    st.warning(f"🤔 Found {len(partial_duplicates_info)} partial match(es) that need your review")
    st.info("These records match either by title OR abstract only. Please review and decide if they are true duplicates.")
    
    # Initialize session state for user decisions if not exists
    if 'partial_duplicate_decisions' not in st.session_state:
        st.session_state.partial_duplicate_decisions = {}
    
    for i, dup in enumerate(partial_duplicates_info):
        key = f"partial_dup_{i}"
        
        with st.expander(f"🔍 Partial Match #{i+1}: {dup['new_record'].get('title', 'No title')[:60]}..."):
            st.markdown("### 📋 Record Comparison")
            
            # Determine match type and get all matching records
            all_matches = []
            match_types = []
            
            if dup['title_duplicates']:
                all_matches.extend(dup['title_duplicates'])
                match_types.append("Title Match")
            
            if dup['abstract_duplicates']:
                all_matches.extend(dup['abstract_duplicates'])
                match_types.append("Abstract Match")
            
            # Remove duplicates if same record appears in both lists
            unique_matches = []
            seen_ids = set()
            for match in all_matches:
                if match[3] not in seen_ids:  # match[3] is the ID
                    unique_matches.append(match)
                    seen_ids.add(match[3])
            
            st.markdown(f"**Match Type:** {' & '.join(match_types)}")
            
            # Display each matching record
            for j, original_record in enumerate(unique_matches):
                st.markdown(f"#### Comparison #{j+1}")
                
                # Side by side comparison
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("##### 📄 Original Record (in database)")
                    st.write(f"**Title:** {original_record[0]}")
                    st.write(f"**Abstract:** {original_record[4] if original_record[4] and original_record[4].strip() else '❌ No abstract available'}")
                    st.write(f"**Year:** {original_record[2] if original_record[2] else 'N/A'}")
                    st.write(f"**Source:** {original_record[1]}")
                
                with col2:
                    st.markdown("##### 🆕 New Record (to be added)")
                    st.write(f"**Title:** {dup['new_record'].get('title', 'N/A')}")
                    new_abstract = dup['new_record'].get('abstract', '')
                    st.write(f"**Abstract:** {new_abstract if new_abstract and new_abstract.strip() else '❌ No abstract available'}")
                    st.write(f"**Year:** {dup['new_record'].get('year', 'N/A')}")
                    st.write(f"**Source:** {dup['source_name']}")
                
                if j < len(unique_matches) - 1:
                    st.divider()
            
            st.divider()
            
            # User decision
            decision = st.radio(
                "What would you like to do with this record?",
                options=["⏳ Review Later", "🚫 It's a duplicate - Don't add", "✅ It's unique - Add to database"],
                key=f"decision_{key}",
                index=0
            )
            
            # Store decision in session state
            st.session_state.partial_duplicate_decisions[key] = {
                'decision': decision,
                'record': dup['new_record'],
                'source_name': dup['source_name']
            }
            
            if decision == "✅ It's unique - Add to database":
                st.success("✅ This record will be added to the database.")
            elif decision == "🚫 It's a duplicate - Don't add":
                st.error("🚫 This record will be skipped.")
    
    # Add process decisions button
    if any(d['decision'] != "⏳ Review Later" for d in st.session_state.partial_duplicate_decisions.values()):
        st.divider()
        if st.button("💾 Process My Decisions", type="primary", use_container_width=True):
            process_partial_duplicate_decisions()

def process_partial_duplicate_decisions():
    """
    Process user decisions for partial duplicates
    """
    if 'partial_duplicate_decisions' not in st.session_state:
        return
    
    records_to_add = []
    decisions = st.session_state.partial_duplicate_decisions
    
    for key, decision_info in decisions.items():
        if decision_info['decision'] == "✅ It's unique - Add to database":
            records_to_add.append({
                'record': decision_info['record'],
                'source_name': decision_info['source_name']
            })
    
    if records_to_add:
        # Store the approved records
        conn = create_database('research_analytics.db')
        cursor = conn.cursor()
        
        stored_count = 0
        try:
            for item in records_to_add:
                store_record_in_database(cursor, item['record'], item['source_name'])
                stored_count += 1
            conn.commit()
            st.success(f"✅ Successfully added {stored_count} record(s) to the database!")
            
            # Clear the decisions from session state
            st.session_state.partial_duplicate_decisions = {}
            st.rerun()
            
        except Exception as e:
            conn.rollback()
            st.error(f"❌ Error adding records: {str(e)}")
        finally:
            conn.close()
    else:
        st.info("ℹ️ No records were selected to be added.")

def display_duplicates_analysis(duplicates_info: List[Dict]):
    """
    Display detailed duplicate analysis
    """
    if duplicates_info:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader("Duplicate Records Analysis")
        with col2:
            duplicates_df = get_duplicates_for_export(duplicates_info)
            if not duplicates_df.empty:
                create_excel_download_button(
                    duplicates_df,
                    "duplicates_analysis",
                    "Export Duplicates",
                    "export_duplicates"
                )

    if not duplicates_info:
        st.success("🎉 No full duplicates found!")
        return
    
    st.warning(f"⚠️ Found {len(duplicates_info)} full duplicate(s)")
    
    for i, dup in enumerate(duplicates_info):
        with st.expander(f"Duplicate #{i+1}: {dup['new_record'].get('title', 'No title')[:80]}..."):
            st.write("**New Record Details:**")
            
            # Display new record information
            st.write(f"**Source:** {dup['source_name']}")
            st.write(f"**Year:** {dup['new_record'].get('year', 'N/A')}")
            st.write(f"**Duplicate Type:** {', '.join(dup['duplicate_type'])}")
            
            # Display the new record's title and abstract for reference
            st.write(f"**Title:** {dup['new_record'].get('title', 'N/A')}")
            if dup['new_record'].get('abstract'):
                st.write(f"**Abstract:** {dup['new_record'].get('abstract', 'N/A')[:200]}...")
            
            st.divider()
            
            # Display title duplicates if found
            if dup['title_duplicates']:
                st.write("**🔍 Title Duplicates Found:**")
                # Updated to handle 5 columns: title, source, year, id, abstract
                title_df = pd.DataFrame(dup['title_duplicates'], 
                                       columns=['Title', 'Source', 'Year', 'ID', 'Abstract'])
                # Display only the relevant columns for the user
                display_title_df = title_df[['Title', 'Source', 'Year']].copy()
                st.dataframe(display_title_df, use_container_width=True)
            
            # Display abstract duplicates if found
            if dup['abstract_duplicates']:
                st.write("**📝 Abstract Duplicates Found:**")
                # Updated to handle 5 columns: title, source, year, id, abstract
                abstract_df = pd.DataFrame(dup['abstract_duplicates'], 
                                         columns=['Title', 'Source', 'Year', 'ID', 'Abstract'])
                # Display only the relevant columns for the user
                display_abstract_df = abstract_df[['Title', 'Source', 'Year']].copy()
                st.dataframe(display_abstract_df, use_container_width=True)
            
            # Add some spacing between duplicates
            if i < len(duplicates_info) - 1:
                st.write("")
                
def display_enhanced_statistics(db_path: str = 'research_analytics.db'):
    """
    Display enhanced statistics with better formatting
    """
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("Database Statistics")
    with col2:
        try:
            stats_data = get_statistics_for_export(db_path)
            create_excel_download_button(
                stats_data,
                "database_statistics",
                "Export Statistics",
                "export_statistics"
            )
        except Exception as e:
            st.error(f"Error preparing statistics export: {str(e)}")
    
    stats = get_statistics(db_path)
    
    # Overview metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("📚 Total Articles", f"{stats['total_articles']:,}")
    with col2:
        st.metric("👥 Total Authors", f"{stats['total_authors']:,}")
    with col3:
        st.metric("📖 Total Journals", f"{stats['total_journals']:,}")
    with col4:
        st.metric("🏷️ Total Keywords", f"{stats['total_keywords']:,}")
    with col5:
        st.metric("🗂️ Total Sources", f"{stats['total_sources']:,}")
    
    # Articles by source
    if stats['articles_by_source']:
        st.subheader("📊 Articles by Source")
        source_df = pd.DataFrame(stats['articles_by_source'], columns=['Source', 'Count'])
        st.bar_chart(source_df.set_index('Source'))
        st.dataframe(source_df, use_container_width=True)
    
    # Articles by year
    if stats['articles_by_year']:
        st.subheader("📅 Articles by Year (Top 10)")
        year_df = pd.DataFrame(stats['articles_by_year'], columns=['Year', 'Count'])
        st.line_chart(year_df.set_index('Year'))
        st.dataframe(year_df, use_container_width=True)
    
    # Top journals and authors side by side
    col1, col2 = st.columns(2)
    
    with col1:
        if stats['top_journals']:
            st.subheader("📖 Top Journals")
            journals_df = pd.DataFrame(stats['top_journals'], columns=['Journal', 'Articles'])
            st.dataframe(journals_df, use_container_width=True)
    
    with col2:
        if stats['top_authors']:
            st.subheader("👥 Most Productive Authors")
            authors_df = pd.DataFrame(stats['top_authors'], columns=['Author', 'Articles'])
            st.dataframe(authors_df, use_container_width=True)
    
    # Top keywords
    if stats['top_keywords']:
        st.subheader("🏷️ Top Keywords")
        keywords_df = pd.DataFrame(stats['top_keywords'], columns=['Keyword', 'Occurrences'])
        st.dataframe(keywords_df, use_container_width=True)
