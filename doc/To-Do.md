# To-Do

Step-by-step development plan for `recruitment-pipeline-os`.

## MVP Goal

The first version should support:

- [x] Company submits hiring request
- [x] System creates structured job brief
- [x] System ranks candidates
- [] System creates shortlist report
- [] Human can review before requesting interview
- [] Proper GDPR

## 0.1. General Project Setup

- [x] Decide tech stack (TUI)
- [x] Create project structure
- [] Set up database (json for now)
- [x] Add environment variables
- [x] Add basic documentation
- [] Add license

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
- [x] Generate target job titles
- [x] Generate required and optional skill lists
- [x] Generate search keywords
- [x] Define candidate exclusion rules
- [x] Create a search strategy for the specific job opening

## 4. Candidate Sourcing

- [x] Build Sourcer logic
- [x] Define which candidate source to use (1 Strong for now: Linkedin?)
- [x] Search for candidates based on the specific job opening
- [x] Extract candidate profile data from source
- [x] Store candidate source and evidence
- [x] Save raw source links for verification

## 5. Candidate Matching

- [x] Build candidate scoring system
- [x] Compare candidates against the job brief
- [x] Score must-have skills
- [x] Score experience and seniority
- [x] Score location and work model fit
- [x] Score nice-to-have skills
- [x] Generate match explanations

## 6. Candidate Review

- [] Create candidate review summary
- [] Highlight why the candidate fits
- [] Highlight possible concerns
- [] Mark candidate as Shortlist, Hold, or Reject
- [] Store review reasoning

## 7. Compliance / Admin Review

- [] Check that candidate reasoning is job-relevant
- [] Remove bias-sensitive reasoning
- [] Check for missing evidence
- [] Approve or remove candidates before delivery

## 8. Client Delivery

- [] Generate client-ready candidate reports
- [] Include match score
- [] Include why the candidate was selected
- [] Include risks or concerns
- [] Include suggested interview questions
- [] Include contact details
- [] Export shortlist as PDF

## 9. Feedback Loop

- [] Feedback can be given when a search is done. 
- [] Account Manager updates current structured job brief
- [] TUI will ask if they want to rerun 