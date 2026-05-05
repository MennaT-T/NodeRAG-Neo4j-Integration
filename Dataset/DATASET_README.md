# Q&A Dataset Generation Summary

## Generated File
**Filename**: `qa_dataset_20260204_011255.csv`  
**Size**: 1.24 GB (1,300,103,299 bytes)  
**Total Rows**: 115,290 rows (+ 1 header row)  
**Generated**: February 4, 2026 at 01:12:55 AM

## Dataset Structure

### Columns (8 total)
1. **Job Title** - The job position title
2. **Job Description** - Full job description text
3. **Question** - Interview question for the position
4. **Resume File Name** - Name of the resume PDF file
5. **Latex_Code** - LaTeX code representation of the resume
6. **LLM Answer** - (Empty) To be filled with LLM-generated answers
7. **Tokens** - (Empty) To be filled with token count
8. **Time** - (Empty) To be filled with generation time

## Data Sources

1. **selected_resumes_for_jobs.json** - 11 job titles, 110 selected resumes
2. **job_title_des.csv** - Job descriptions for 15 job titles
3. **job_title_questions.csv** - 7 questions per job title (15 titles)
4. **resume_dataset_with_latex.csv** - 1,162 resumes with LaTeX code

## Dataset Composition

### Rows per Job Title

| Job Title | Descriptions | Questions | Resumes | Total Rows |
|-----------|-------------|-----------|---------|------------|
| Backend Developer | 147 | 7 | 10 | 10,290 |
| Database Administrator | 139 | 7 | 10 | 9,730 |
| DevOps Engineer | 155 | 7 | 10 | 10,850 |
| Django Developer | 152 | 7 | 10 | 10,640 |
| Full Stack Developer | 138 | 7 | 10 | 9,660 |
| Java Developer | 161 | 7 | 10 | 11,270 |
| JavaScript Developer | 166 | 7 | 10 | 11,620 |
| Machine Learning | 152 | 7 | 10 | 10,640 |
| Network Administrator | 145 | 7 | 10 | 10,150 |
| Software Engineer | 160 | 7 | 10 | 11,200 |
| Wordpress Developer | 132 | 7 | 10 | 9,240 |
| **TOTAL** | - | - | - | **115,290** |

## Generation Logic

For each job title:
- **Cartesian Product**: Descriptions × Questions × Resumes
- Formula: `rows = num_descriptions × num_questions × num_resumes`
- Each job title has 7 questions (from job_title_questions.csv)
- Each job title has 10 selected resumes (from selected_resumes_for_jobs.json)
- Number of descriptions varies by job title (from job_title_des.csv)

## Example Row

```
Job Title: Backend Developer
Job Description: "We are seeking a Backend Developer to join our application development team..."
Question: "What backend languages and frameworks have you used, and which are you strongest in?"
Resume File Name: 1037_DotNet Developer.pdf
Latex_Code: [12,006 characters of LaTeX code]
LLM Answer: [Empty - to be filled]
Tokens: [Empty - to be filled]
Time: [Empty - to be filled]
```

## Next Steps

The dataset is ready for LLM answer generation. For each row:
1. Use the combination of Job Description, Question, and Latex_Code as input
2. Generate an answer using an LLM
3. Record the answer in the "LLM Answer" column
4. Record token count in the "Tokens" column
5. Record generation time in the "Time" column

## Generation Script

**Script**: `generate_qa_dataset.py`  
**Location**: `Dataset/generate_qa_dataset.py`

To regenerate the dataset, run:
```bash
python Dataset/generate_qa_dataset.py
```

## Notes

- All selected resumes were chosen based on:
  - **Diversity**: Distributed across matching work field categories
  - **Content Length**: Longest LaTeX code lengths selected
- Empty columns (LLM Answer, Tokens, Time) are intentionally left blank for future processing
- The dataset size is large (1.24 GB) due to the inclusion of full LaTeX code for each resume

