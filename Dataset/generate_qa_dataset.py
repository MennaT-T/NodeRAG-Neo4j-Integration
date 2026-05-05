"""
Generate comprehensive Q&A dataset by combining job descriptions, questions, and resumes.

This script creates a Cartesian product of:
- Job titles (from selected_resumes_for_jobs.json)
- Job descriptions (from job_title_des.csv)
- Questions (from job_title_questions.csv)
- Selected resumes (from selected_resumes_for_jobs.json)

Output: A CSV with columns for LLM-based answer generation.
"""
import csv
import json
from datetime import datetime

print("=" * 80)
print("Generating Q&A Dataset")
print("=" * 80)

# 1. Load selected resumes JSON
print("\n[1/5] Loading selected resumes...")
with open('Dataset/selected_resumes_for_jobs.json', 'r', encoding='utf-8') as f:
    selected_resumes = json.load(f)

print(f"      Loaded {len(selected_resumes)} job titles with selected resumes")

# 2. Load job descriptions CSV
print("\n[2/5] Loading job descriptions...")
job_descriptions = {}  # {job_title: [list of descriptions]}
with open('Dataset/job_title_des.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        job_title = row['Job Title'].strip()
        job_desc = row['Job Description'].strip()
        
        if job_title not in job_descriptions:
            job_descriptions[job_title] = []
        job_descriptions[job_title].append(job_desc)

print(f"      Loaded job descriptions for {len(job_descriptions)} job titles")

# 3. Load questions CSV
print("\n[3/5] Loading questions...")
questions = {}  # {job_title: [list of questions]}
with open('Dataset/job_title_questions.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        job_title = row['Job Title'].strip()
        question = row['Question'].strip()
        
        if job_title not in questions:
            questions[job_title] = []
        questions[job_title].append(question)

print(f"      Loaded questions for {len(questions)} job titles")

# 4. Load resume latex codes
print("\n[4/5] Loading resume latex codes...")
resume_latex = {}  # {resume_id: latex_code}
with open('Dataset/resume_dataset_with_latex.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        resume_id = row['ID'].strip()
        latex_code = row.get('Latex_Code', '').strip()
        resume_latex[resume_id] = latex_code

print(f"      Loaded latex codes for {len(resume_latex)} resumes")

# 5. Generate dataset rows
print("\n[5/5] Generating dataset rows...")
output_rows = []
total_combinations = 0
job_title_stats = {}

for job_title, resumes in selected_resumes.items():
    # Get job descriptions for this title
    job_descs = job_descriptions.get(job_title, [])
    if not job_descs:
        print(f"      [WARNING] No job descriptions found for: {job_title}")
        continue
    
    # Get questions for this title
    job_questions = questions.get(job_title, [])
    if not job_questions:
        print(f"      [WARNING] No questions found for: {job_title}")
        continue
    
    # Count combinations for this job title
    num_combinations = len(job_descs) * len(job_questions) * len(resumes)
    job_title_stats[job_title] = {
        'descriptions': len(job_descs),
        'questions': len(job_questions),
        'resumes': len(resumes),
        'total_rows': num_combinations
    }
    total_combinations += num_combinations
    
    print(f"      Processing {job_title}:")
    print(f"        - {len(job_descs)} job descriptions")
    print(f"        - {len(job_questions)} questions")
    print(f"        - {len(resumes)} resumes")
    print(f"        = {num_combinations} rows")
    
    # Generate all combinations
    for job_desc in job_descs:
        for question in job_questions:
            for resume in resumes:
                resume_id = resume['resume_id']
                resume_filename = resume['filename']
                latex_code = resume_latex.get(resume_id, '')
                
                row = {
                    'Job Title': job_title,
                    'Job Description': job_desc,
                    'Question': question,
                    'Resume File Name': resume_filename,
                    'Latex_Code': latex_code,
                    'LLM Answer': '',
                    'Tokens': '',
                    'Time': ''
                }
                output_rows.append(row)

# 6. Write to CSV
output_filename = f'Dataset/qa_dataset_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
print(f"\n[6/6] Writing {len(output_rows)} rows to CSV...")

with open(output_filename, 'w', newline='', encoding='utf-8') as f:
    fieldnames = ['Job Title', 'Job Description', 'Question', 'Resume File Name', 
                  'Latex_Code', 'LLM Answer', 'Tokens', 'Time']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    
    writer.writeheader()
    writer.writerows(output_rows)

print(f"      Successfully wrote to: {output_filename}")

# Print summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Total job titles processed: {len(job_title_stats)}")
print(f"Total rows generated: {len(output_rows)}")
print(f"\nBreakdown by Job Title:")
print("-" * 80)
for job_title, stats in sorted(job_title_stats.items()):
    print(f"{job_title}:")
    print(f"  {stats['descriptions']} descriptions × {stats['questions']} questions × {stats['resumes']} resumes = {stats['total_rows']} rows")

print("\n" + "=" * 80)
print(f"[SUCCESS] Dataset generated successfully!")
print(f"  Output file: {output_filename}")
print(f"  Total rows: {len(output_rows)}")
print("=" * 80)

