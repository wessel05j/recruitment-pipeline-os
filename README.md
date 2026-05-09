### recruitment-pipeline-os

V1 of `recruitment-pipeline-os` is a terminal-based recruitment pipeline for finding developer and IT candidates from public GitHub data.

It takes a rough hiring request and turns it into a structured process: job understanding, GitHub search planning, candidate sourcing, candidate review, admin review, ranked shortlist formatting, and a client-ready PDF report.

Creator: Erich Johannes Wessel  
Repository: https://github.com/wessel05j/recruitment-pipeline-os

Important V1 limitation: this works best for technical roles where GitHub activity is a useful signal. It is not a general-purpose recruiting database, and it should not be used as a final hiring decision system.

### Setup

## 1. Clone repo

```bash
git clone https://github.com/wessel05j/recruitment-pipeline-os
cd recruitment-pipeline-os
```

## 2. Create venv

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 3. Environment variables

Create your local `.env` file from the example.

macOS / Linux:

```bash
cp .env.example .env
```

Windows:

```powershell
Copy-Item .env.example .env
```

Add your keys:

```bash
GITHUB_TOKEN=your_token_here
OPENAI_API_KEY=your_token_here
```

## 4. Run project

```bash
python main.py
```

The final PDF is generated at:

```text
app/output/github_candidate_shortlist.pdf
```

Temporary pipeline files under `app/temp/` are cleaned after a successful run.

### Pipeline

<img width="1672" height="941" alt="Recruitment Agency Pipeline" src="https://github.com/user-attachments/assets/ec9ccb49-74f8-45ed-b586-451c2532d201" />
