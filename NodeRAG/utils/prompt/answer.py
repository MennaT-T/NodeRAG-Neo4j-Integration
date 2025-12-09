answer_prompt = """
You are helping a job candidate answer an application question.
Generate a first-person response (using "I", "my", "me") as if the
candidate is writing it themselves.

CANDIDATE PROFILE:
{info}

JOB CONTEXT (if available):
{job_context}

PREVIOUS ANSWERS (for style consistency):
{qa_history}

QUESTION:
{query}

INSTRUCTIONS:
1. Write in first person (I/my/me) - never use third person
2. Be specific and authentic - reference actual experiences
3. Reference specific projects, achievements, or skills
4. Match the writing style of previous answers (if available)
5. Keep it concise but informative (2-3 paragraphs, 150-300 words)
6. Show enthusiasm and genuine interest
7. Avoid generic statements - be concrete and personal
8. Connect your interest to specific experiences or projects
9. Tailor your answer to the job description when relevant

ANSWER (write as the candidate):
"""


answer_prompt_Chinese = '''
---ΦºÆΦë▓---
Σ╜áµÿ»Σ╕ÇΣ╕¬µá╣µì«µúÇτ┤óσê░τÜäΣ┐íµü»σ¢₧τ¡öΘù«ΘóÿτÜäτ╗åΦç┤σè⌐µëïπÇé

---τ¢«µáç---
µÅÉΣ╛¢µ╕àµÖ░Σ╕öσçåτí«τÜäσ¢₧τ¡öπÇéΣ╗öτ╗åσ«íµƒÑσÆîΘ¬îΦ»üµúÇτ┤óσê░τÜäµò░µì«∩╝îσ╣╢τ╗ôσÉêΣ╗╗Σ╜òτ¢╕σà│τÜäσ┐àΦªüτƒÑΦ»å∩╝îσà¿Θ¥óσ£░Φºúσå│τö¿µê╖τÜäΘù«ΘóÿπÇé
σªéµ₧£Σ╜áΣ╕ìτí«σ«Üτ¡öµíê∩╝îΦ»╖τ¢┤µÄÑΦ»┤µÿÄΓÇöΓÇöΣ╕ìΦªüτ╝ûΘÇáΣ┐íµü»πÇé
Σ╕ìΦªüσîàσÉ½µ▓íµ£ëµÅÉΣ╛¢µö»µîüΦ»üµì«τÜäτ╗åΦèéπÇé

---Φ╛ôσàÑ---
µúÇτ┤óσê░τÜäΣ┐íµü»∩╝Ü{info}

τö¿µê╖Θù«Θóÿ∩╝Ü{query}
'''
