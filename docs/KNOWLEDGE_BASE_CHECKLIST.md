# CampusAI — Knowledge Base Document Checklist

Collect these from the official college website, departments, exam branch, and admin office.
Tick each one as you add it to `backend/data/<folder>/`.

## 1. general/
- [ ] About the college (history, established year, affiliation, autonomous status)
- [ ] Vision & mission, management/trust details
- [ ] Accreditations & rankings (NAAC grade, NBA programs, NIRF rank)
- [ ] Principal / Dean / HOD contact directory, office timings, address & map
- [ ] Frequently asked questions (write your own short FAQ .md — this boosts answer quality a lot)

## 2. admissions/
- [ ] Admission brochure / prospectus
- [ ] Courses offered with intake per branch (B.Tech, M.Tech, MBA if any)
- [ ] Eligibility criteria and entrance exams (EAPCET/EAMCET, ECET lateral entry, PGECET)
- [ ] Convener vs management (Category-B) quota process
- [ ] Documents required at admission, important dates, counselling codes

## 3. fees/
- [ ] Tuition fee structure (per year, per branch, per quota)
- [ ] Hostel fee, bus/transport fee, exam fee, other charges
- [ ] Scholarships and fee reimbursement (state schemes, merit scholarships)
- [ ] Fee payment modes, deadlines, late-fee and refund policy

## 4. academics/
- [ ] Academic regulations (R22 / R23 etc.) — credits, promotion rules
- [ ] Course structure & syllabus for every branch and year
- [ ] Academic calendar for the current year
- [ ] Elective lists, honors/minor degree rules, MOOC/NPTEL credit transfer

## 5. examinations/
- [ ] Exam regulations (internal + external marks split, pass criteria)
- [ ] Grading system and CGPA/SGPA calculation, % conversion formula
- [ ] Mid-term and semester exam timetables
- [ ] Revaluation, recounting, supplementary exam procedure and fees
- [ ] Malpractice rules, hall-ticket rules

## 6. departments/  (one file per department)
- [ ] CSE, IT, ECE, EEE, CSE-AIML, etc.: HOD, faculty list with qualifications, labs, intake
- [ ] Department achievements, research centers, student chapters (IEEE, CSI, ACM)

## 7. placements/
- [ ] Placement statistics (year-wise: companies, offers, highest/average package)
- [ ] List of recruiters
- [ ] Training & Placement cell policy (eligibility, one-offer rule, dream-company rule)
- [ ] Internship policy, MoUs with industry

## 8. facilities/
- [ ] Library (timings, borrowing rules, e-resources)
- [ ] Hostel (rooms, mess, rules, warden contacts)
- [ ] Transport (bus routes, stops, timings)
- [ ] Labs, sports, gym, canteen, medical room, Wi-Fi, auditorium

## 9. student_life/
- [ ] Clubs and societies, cultural/technical fests
- [ ] NSS / NCC, sports events, hackathons
- [ ] Student council, mentoring system

## 10. policies/
- [ ] Code of conduct & discipline rules
- [ ] Attendance policy (minimum %, condonation)
- [ ] Anti-ragging policy and committee contacts
- [ ] Grievance redressal, Internal Complaints Committee, women's safety cell

## 11. notices/
- [ ] Current circulars (holidays, events, exam notices) — remove expired ones

---

## Quality rules
1. **Official sources only** — the bot is only as accurate as what you feed it.
2. **Text PDFs, not scans.** Test: if you can't select text in the PDF, OCR it first.
3. **One topic per file, clear filenames** — e.g. `fee_structure_2026_27.pdf`, not `doc1.pdf`. Filenames appear as citations.
4. **Tables** (fees, timetables): also write a short .md version — tables often extract badly from PDFs.
5. **Keep it current** — put the academic year in filenames and delete outdated versions.
6. **Build a test set** — write 30–50 real questions with known answers and check the bot after every change.
