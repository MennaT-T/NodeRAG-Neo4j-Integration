"""
Create Benchmark Dataset from Testing CSV
==========================================
This script:
1. Takes the qa_dataset_testing CSV
2. Selects 3 random job descriptions per unique resume
3. Keeps the 7 existing questions from the CSV for each job-resume pair
4. Adds 4 additional benchmark questions for each job-resume pair
5. Adds a "category" column based on question type
6. Creates a new CSV for benchmarking

Usage: python Dataset/create_benchmark_dataset.py
"""

import pandas as pd
import random
import sys
import os
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Get script directory for robust path handling
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TESTING_CSV_PATH = os.path.join(SCRIPT_DIR, "qa_dataset_testing_20260204_183215.csv")
OUTPUT_DIR = SCRIPT_DIR

# User ID to Resume filename mapping
USER_RESUME_MAPPING = {
    "user_36": "1037_DotNet Developer.pdf",
    "user_37": "1030_DotNet Developer.pdf",
    "user_38": "1029_DotNet Developer.pdf",
    "user_39": "1043_DotNet Developer.pdf",
    "user_40": "786_Python Developer.pdf",
    "user_41": "1036_DotNet Developer.pdf",
    "user_42": "767_Python Developer.pdf",
    "user_43": "782_Python Developer.pdf",
    "user_44": "797_Python Developer.pdf",
    "user_45": "792_Python Developer.pdf"
}

# Reverse mapping: Resume filename to User ID
RESUME_TO_USER_ID = {v: k for k, v in USER_RESUME_MAPPING.items()}

# Additional benchmark questions (not in CSV)
ADDITIONAL_QUESTIONS = [
    {"question": "What programming languages and tools are you proficient in?", "category": "technical_skills"},
    {"question": "Tell me about a challenging project you worked on.", "category": "experience"},
    {"question": "What is your educational background?", "category": "education"},
    {"question": "Describe your experience working in a team.", "category": "soft_skills"}
]

# Exact question to category mapping
# Based on the 7 unique questions in qa_dataset_testing CSV
EXACT_QUESTION_CATEGORY_MAP = {
    # Technical Skills (5 questions about technical capabilities and approaches)
    "What backend languages and frameworks have you used, and which are you strongest in?": "technical_skills",
    "How do you design and document RESTful (or GraphQL) APIs for maintainability and scalability?": "technical_skills",
    "What is your approach to database schema design and optimizing queries for performance?": "technical_skills",
    "How do you ensure backend reliability (testing, monitoring, error handling) in production?": "technical_skills",
    
    # Experience (1 question about past work)
    "Describe a backend system you built or improved—what were the main challenges and how did you solve them?": "experience",
    
    # Motivation (2 questions about interest and fit)
    "Why do you want to apply to this position?": "motivation",
    "Why are you interested in joining our company?": "motivation"
}

# Partial matching fallback for questions not in exact map
QUESTION_CATEGORY_KEYWORDS = {
    # Motivation
    "why do you want": "motivation",
    "why are you interested": "motivation",
    "interested in joining": "motivation",
    "good fit": "motivation",
    
    # Experience
    "backend system you built": "experience",
    "system you built or improved": "experience",
    "challenging project": "experience",
    "tell me about a challenging": "experience",
    
    # Technical Skills
    "backend languages and frameworks": "technical_skills",
    "programming languages and tools": "technical_skills",
    "what programming languages": "technical_skills",
    "design and document": "technical_skills",
    "restful": "technical_skills",
    "graphql": "technical_skills",
    "database schema": "technical_skills",
    "optimizing queries": "technical_skills",
    "backend reliability": "technical_skills",
    "testing, monitoring": "technical_skills",
    "proficient in": "technical_skills",
    "machine learning": "technical_skills",
    "data science": "technical_skills",
    
    # Education
    "education": "education",
    "educational background": "education",
    "degree": "education",
    "university": "education",
    
    # Soft Skills
    "working in a team": "soft_skills",
    "experience working in a team": "soft_skills",
    "team": "soft_skills",
    "stay updated": "soft_skills",
    "communication": "soft_skills",
    "leadership": "soft_skills"
}

def categorize_question(question_text: str) -> str:
    """Determine the category of a question based on its content."""
    # First try exact match
    if question_text in EXACT_QUESTION_CATEGORY_MAP:
        return EXACT_QUESTION_CATEGORY_MAP[question_text]
    
    # Then try partial keyword matching
    question_lower = question_text.lower()
    for keyword, category in QUESTION_CATEGORY_KEYWORDS.items():
        if keyword in question_lower:
            return category
    
    # Default to "technical_skills" if no match found
    return "technical_skills"


def main():
    print("\n" + "="*70)
    print("  BENCHMARK DATASET CREATOR")
    print("="*70)
    
    print(f"\n📂 Loading testing dataset...")
    try:
        df = pd.read_csv(TESTING_CSV_PATH, encoding='utf-8', low_memory=False)
        print(f"   ✓ Loaded {len(df):,} rows")
    except FileNotFoundError:
        print(f"❌ Error: File not found: {TESTING_CSV_PATH}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error loading dataset: {e}")
        sys.exit(1)
    
    # Get unique resumes
    unique_resumes = df['Resume File Name'].unique()
    print(f"\n📊 Found {len(unique_resumes)} unique resumes")
    
    # Verify all resumes are in our mapping
    for resume in unique_resumes:
        if resume not in RESUME_TO_USER_ID:
            print(f"⚠️  Warning: Resume '{resume}' not in user mapping!")
    
    print(f"\n🎯 Creating benchmark dataset...")
    print(f"   • 3 job descriptions per resume")
    print(f"   • Keeping existing questions from CSV")
    print(f"   • Adding {len(ADDITIONAL_QUESTIONS)} benchmark questions per job-resume pair")
    
    benchmark_rows = []
    
    for resume_filename in unique_resumes:
        user_id = RESUME_TO_USER_ID.get(resume_filename, "unknown")
        
        # Get all rows for this resume
        resume_df = df[df['Resume File Name'] == resume_filename]
        
        # Get unique job descriptions for this resume
        unique_job_descriptions = resume_df['Job Description'].unique()
        
        print(f"\n   Processing {resume_filename} ({user_id})...")
        print(f"      • Found {len(unique_job_descriptions)} job descriptions")
        
        # Select 3 random job descriptions
        if len(unique_job_descriptions) <= 3:
            selected_jobs = unique_job_descriptions
            print(f"      • Using all {len(selected_jobs)} job descriptions")
        else:
            selected_jobs = random.sample(list(unique_job_descriptions), 3)
            print(f"      • Selected 3 random job descriptions")
        
        for job_idx, job_description in enumerate(selected_jobs, 1):
            # Get all questions for this job-resume pair from CSV
            job_resume_rows = resume_df[resume_df['Job Description'] == job_description]
            
            print(f"      • Job {job_idx}: {len(job_resume_rows)} existing questions")
            
            # Add existing questions from CSV with all original columns + new columns
            for _, row in job_resume_rows.iterrows():
                category = categorize_question(row['Question'])
                benchmark_rows.append({
                    'Job Title': row['Job Title'],
                    'Job Description': job_description,
                    'Question': row['Question'],
                    'Resume File Name': resume_filename,
                    'Latex_Code': row['Latex_Code'],
                    'LLM Answer': row['LLM Answer'],
                    'Tokens': row['Tokens'],
                    'Time': row['Time'],
                    'User ID': user_id,
                    'Category': category,
                    'NodeRAG Answer': '',  # Empty - to be filled by NodeRAG
                    'NodeRAG Tokens': '',  # Empty - to be filled by NodeRAG
                    'NodeRAG Time': '',   # Empty - to be filled by NodeRAG
                    'Source': 'csv'
                })
            
            # Add additional benchmark questions (no LLM answer, no Latex_Code)
            for additional_q in ADDITIONAL_QUESTIONS:
                benchmark_rows.append({
                    'Job Title': job_resume_rows.iloc[0]['Job Title'],  # Use same job title
                    'Job Description': job_description,
                    'Question': additional_q['question'],
                    'Resume File Name': resume_filename,
                    'Latex_Code': job_resume_rows.iloc[0]['Latex_Code'],  # Use same latex code
                    'LLM Answer': '',  # Empty - no LLM answer for benchmark questions
                    'Tokens': '',      # Empty - no LLM tokens for benchmark questions
                    'Time': '',        # Empty - no LLM time for benchmark questions
                    'User ID': user_id,
                    'Category': additional_q['category'],
                    'NodeRAG Answer': '',  # Empty - to be filled by NodeRAG
                    'NodeRAG Tokens': '',  # Empty - to be filled by NodeRAG
                    'NodeRAG Time': '',   # Empty - to be filled by NodeRAG
                    'Source': 'benchmark'
                })
            
            print(f"         → Added {len(job_resume_rows)} CSV questions + {len(ADDITIONAL_QUESTIONS)} benchmark questions")
    
    # Create DataFrame
    benchmark_df = pd.DataFrame(benchmark_rows)
    
    print(f"\n📊 BENCHMARK DATASET SUMMARY:")
    print(f"   • Total Rows: {len(benchmark_df):,}")
    print(f"   • Unique Resumes: {benchmark_df['Resume File Name'].nunique()}")
    print(f"   • Unique Job Descriptions: {benchmark_df['Job Description'].nunique()}")
    print(f"   • Questions per Resume: {len(benchmark_df) / len(unique_resumes):.1f}")
    
    print(f"\n📊 BREAKDOWN BY CATEGORY:")
    category_counts = benchmark_df['Category'].value_counts()
    for category, count in category_counts.items():
        percentage = (count / len(benchmark_df)) * 100
        print(f"   • {category}: {count} ({percentage:.1f}%)")
    
    print(f"\n📊 BREAKDOWN BY SOURCE:")
    source_counts = benchmark_df['Source'].value_counts()
    for source, count in source_counts.items():
        percentage = (count / len(benchmark_df)) * 100
        print(f"   • {source}: {count} ({percentage:.1f}%)")
    
    # Save to CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"benchmark_dataset_{timestamp}.csv"
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    
    print(f"\n💾 Saving dataset...")
    benchmark_df.to_csv(output_path, index=False, encoding='utf-8')
    print(f"   ✓ Saved to: {output_filename}")
    
    # Show sample
    print(f"\n📋 SAMPLE ROWS (first 3):")
    print("="*70)
    for idx, row in benchmark_df.head(3).iterrows():
        print(f"\nRow {idx + 1}:")
        print(f"   User ID: {row['User ID']}")
        print(f"   Resume: {row['Resume File Name']}")
        print(f"   Job Title: {row['Job Title']}")
        print(f"   Question: {row['Question'][:60]}...")
        print(f"   Category: {row['Category']}")
        print(f"   Source: {row['Source']}")
        has_llm = 'Yes' if row['LLM Answer'] and str(row['LLM Answer']).strip() else 'No'
        print(f"   Has LLM Answer: {has_llm}")
        print(f"   Has Latex Code: {'Yes' if row['Latex_Code'] else 'No'}")
    
    print(f"\n📋 COLUMN STRUCTURE:")
    print("="*70)
    print("Original columns from testing CSV:")
    print("   • Job Title, Job Description, Question, Resume File Name")
    print("   • Latex_Code, LLM Answer, Tokens, Time")
    print("\nNew columns added:")
    print("   • User ID (mapped from resume filename)")
    print("   • Category (categorized question type)")
    print("   • NodeRAG Answer (empty - to be filled)")
    print("   • NodeRAG Tokens (empty - to be filled)")
    print("   • NodeRAG Time (empty - to be filled)")
    print("   • Source (csv or benchmark)")
    
    print("\n" + "="*70)
    print("  ✅ BENCHMARK DATASET CREATED SUCCESSFULLY")
    print("="*70)
    print(f"\n📁 Output file: {output_filename}")
    print(f"📊 Total rows: {len(benchmark_df):,}")
    print(f"👥 Users covered: {', '.join(sorted(benchmark_df['User ID'].unique()))}")
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    random.seed(42)  # For reproducibility
    main()

