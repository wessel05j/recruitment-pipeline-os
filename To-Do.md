# To-Do

Step-by-step development plan for `recruitment-pipeline-os`.

## MVP Goal

The first version should support:

- [] Company submits hiring request
- [] System creates structured job brief
- [] System ranks candidates
- [] System creates shortlist report
- [] Human can review before requesting interview
- [] Proper GDPR

## 0.1. General Project Setup

- [] Decide tech stack (TUI)
- [] Create project structure
- [] Set up database (SQLite)
- [] Add environment variables
- [] Add basic documentation
- [] Add license

## 1. Client Input

- [] Create a simple input where a company can submit a hiring request

## 2. Job Understanding

- [] Build Account Manager logic
- [] Extract structured job details from the hiring request
- [] Identify missing information
- [] Generate clarification questions
- [] Save the final structured job brief

## 3. Search Planning

- [] Build Recruitment Consultant logic
- [] Generate target job titles
- [] Generate required and optional skill lists
- [] Generate search keywords
- [] Define candidate exclusion rules
- [] Create a search strategy for the specific job opening

## 4. Candidate Sourcing

- [] Build Sourcer logic
- [] Define which candidate source to use (1 Strong for now: Linkedin?)
- [] Search for candidates based on the specific job opening
- [] Extract candidate profile data from source
- [] Store candidate source and evidence
- [] Save raw source links for verification

## 5. Candidate Matching

- [] Build candidate scoring system
- [] Compare candidates against the job brief
- [] Score must-have skills
- [] Score experience and seniority
- [] Score location and work model fit
- [] Score nice-to-have skills
- [] Generate match explanations

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