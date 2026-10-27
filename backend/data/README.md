# Knowledge base folder

Drop official college documents (PDF / TXT / MD) into the matching sub-folder.
The folder name becomes the document's **category**, which the chat UI can filter on.

| Folder         | Put here |
|----------------|----------|
| general/       | About the college, history, vision/mission, accreditations (NAAC/NBA/NIRF), contact directory, FAQs |
| admissions/    | Admission brochure, eligibility, EAMCET/ECET/management quota process, required documents, important dates |
| fees/          | Fee structure per branch/year, hostel & bus fees, scholarship & fee-reimbursement rules, refund policy |
| academics/     | Syllabus & curriculum (R22/R23 etc.), academic calendar, credit system, academic regulations |
| examinations/  | Exam regulations, timetables, grading/CGPA rules, revaluation, supplementary exam process |
| departments/   | One file per department: HOD, faculty list, labs, programs offered, intake |
| placements/    | Placement statistics, recruiter list, training & placement cell policy, internship rules |
| facilities/    | Library, hostel, transport routes, labs, sports, canteen, medical, Wi-Fi |
| student_life/  | Clubs, events, fests, NSS/NCC, student chapters, anti-ragging committee |
| policies/      | Code of conduct, attendance policy, dress code, anti-ragging, grievance redressal |
| notices/       | Current circulars and notices (replace old ones regularly) |

After adding files run:  `python ingest.py`
(or use the Admin page → "Re-index data folder").

Tips:
- Text-based PDFs only. Scanned PDFs have no text layer — OCR them first (e.g. `ocrmypdf in.pdf out.pdf`).
- Prefer clean, current versions; delete outdated circulars so the bot doesn't quote old dates.
- Tables (fee charts) extract better if you also save them as a short .md / .txt summary.
