# To-Do

Step-by-step development plan for `recruitment-pipeline-os`.

## V1 Status

V1 is now focused and usable for GitHub-based sourcing of developers and IT candidates. It creates a structured job brief, searches GitHub, reviews candidates, ranks approved candidates, and exports a client-ready PDF shortlist.

Known V1 limitations:

- GitHub is the only candidate source.
- It works best for technical roles where public GitHub activity is meaningful.
- Contactability is scored, but missing public email does not remove a candidate.
- Proper GDPR/legal review is still required before production use.

## MVP Goal

The first version supports:

- [x] Company submits hiring request
- [x] System creates structured job brief
- [x] System searches GitHub for candidates
- [x] System ranks candidates
- [x] System creates shortlist report
- [x] Human can review before requesting interview
- [ ] Proper GDPR/legal production review

## 0.1. General Project Setup

- [x] Decide tech stack (TUI)
- [x] Create project structure
- [x] Use JSON files for V1 pipeline state
- [x] Add environment variables
- [x] Add basic documentation
- [ ] Add license

## 1. Client Input

- [x] Create a simple input where a company can submit a hiring request

## 2. Job Understanding

- [x] Build Account Manager logic
- [x] Extract structured job details from the hiring request
- [x] Identify missing information
- [x] Generate clarification questions
- [x] Save the final structured job brief

## 3. Search Planning

- [x] Build Recruitment Consultant logic
- [x] Generate required languages
- [x] Generate signal keys
- [x] Define candidate exclusion rules
- [x] Create a GitHub search strategy for the specific job opening

## 4. Candidate Sourcing

- [x] Build GitHub sourcer logic
- [x] Search by location, language, repositories, followers, and activity
- [x] Check signal keys against bio and repository metadata
- [x] Extract candidate profile data from GitHub
- [x] Store candidate source and evidence
- [x] Save raw source links for verification
- [x] Save funnel metrics

## 5. Candidate Matching

- [x] Build candidate scoring system
- [x] Compare candidates against the job brief
- [x] Score technical/profile fit
- [x] Score contactability separately
- [x] Score location and work model fit when visible
- [x] Generate match explanations

## 6. Candidate Review

- [x] Create candidate review summary
- [x] Highlight why the candidate fits
- [x] Highlight possible concerns
- [x] Mark candidate with sourcing priority
- [x] Store review reasoning

## 7. Compliance / Admin Review

- [x] Check that candidate reasoning is job-relevant
- [x] Avoid known sensitive/non-job-relevant rejection reasons
- [x] Check for serious red flags
- [x] Approve or remove candidates before delivery

## 8. Client Delivery

- [x] Generate client-ready candidate reports
- [x] Include match score
- [x] Include why the candidate was selected
- [x] Include risks or concerns
- [x] Include suggested interview questions
- [x] Include contact details/contactability
- [x] Export shortlist as PDF

## 9. Post-V1 Ideas

- [ ] Add proper GDPR workflow and retention rules
- [ ] Add richer human review controls
- [ ] Add feedback loop after a search is done
- [ ] Let Account Manager update the current structured job brief
- [ ] Let the TUI ask whether to rerun a specific pipeline stage
- [ ] Add more candidate sources beyond GitHub
