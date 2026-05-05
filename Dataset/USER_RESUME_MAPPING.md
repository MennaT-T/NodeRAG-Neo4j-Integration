# User-Resume Mapping

**Generated**: 2026-02-04 19:20:33

This document maps user IDs (36-45) to their corresponding resume files in the ingestion dataset.

## Mapping Table

| User ID | User Name | Resume Filename | Resume # | Category |
|---------|-----------|----------------|----------|----------|
| 36 | User_qa_1 | 1029_DotNet Developer.pdf | 1029 | DotNet Developer |
| 37 | User_qa_2 | 1030_DotNet Developer.pdf | 1030 | DotNet Developer |
| 38 | User_qa_3 | 1036_DotNet Developer.pdf | 1036 | DotNet Developer |
| 39 | User_qa_4 | 1037_DotNet Developer.pdf | 1037 | DotNet Developer |
| 40 | User_qa_5 | 1043_DotNet Developer.pdf | 1043 | DotNet Developer |
| 41 | User_qa_6 | 767_Python Developer.pdf | 767 | Python Developer |
| 42 | User_qa_7 | 782_Python Developer.pdf | 782 | Python Developer |
| 43 | User_qa_8 | 786_Python Developer.pdf | 786 | Python Developer |
| 44 | User_qa_9 | 792_Python Developer.pdf | 792 | Python Developer |
| 45 | User_qa_10 | 797_Python Developer.pdf | 797 | Python Developer |

## Quick Reference

### DotNet Developers
- **User 36** (User_qa_1): 1029_DotNet Developer.pdf
- **User 37** (User_qa_2): 1030_DotNet Developer.pdf
- **User 38** (User_qa_3): 1036_DotNet Developer.pdf
- **User 39** (User_qa_4): 1037_DotNet Developer.pdf
- **User 40** (User_qa_5): 1043_DotNet Developer.pdf

### Python Developers
- **User 41** (User_qa_6): 767_Python Developer.pdf
- **User 42** (User_qa_7): 782_Python Developer.pdf
- **User 43** (User_qa_8): 786_Python Developer.pdf
- **User 44** (User_qa_9): 792_Python Developer.pdf
- **User 45** (User_qa_10): 797_Python Developer.pdf

## Usage

When ingesting Q&A pairs into the backend:
1. Use the `user_id` field to associate questions/answers with the correct user
2. The resume PDFs are located in `Dataset/ingestion_resumes/`
3. The ingestion CSV contains all Q&A pairs for these users

## Python Dictionary

```python
USER_RESUME_MAPPING = {
    36: "1029_DotNet Developer.pdf",  # User_qa_1
    37: "1030_DotNet Developer.pdf",  # User_qa_2
    38: "1036_DotNet Developer.pdf",  # User_qa_3
    39: "1037_DotNet Developer.pdf",  # User_qa_4
    40: "1043_DotNet Developer.pdf",  # User_qa_5
    41: "767_Python Developer.pdf",  # User_qa_6
    42: "782_Python Developer.pdf",  # User_qa_7
    43: "786_Python Developer.pdf",  # User_qa_8
    44: "792_Python Developer.pdf",  # User_qa_9
    45: "797_Python Developer.pdf",  # User_qa_10
}
```

## Backend Integration

When syncing to the backend database, use this mapping to:
- Associate Q&A pairs with the correct user_id
- Link resume documents to user profiles
- Maintain consistency between NodeRAG and backend data
