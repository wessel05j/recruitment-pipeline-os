### recruitment-pipeline-os

A recruitment automation project that simulates the core workflow of a permanent recruitment agency.

The system takes a company’s rough hiring request and turns it into a structured recruitment process: job understanding, search planning, candidate sourcing, candidate matching, quality review, compliance review, and final client-ready shortlist reports.

### How to setup

## 1. Clone Repo
```bash
git clone https://github.com/wessel05j/recruitment-pipeline-os
cd reqruitment-pipeline-os
```

## 2. Create venv

# maxOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

# Windows
```powershell 
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 3. Environment variables

Create your local `.env` file from the example:

# maxOS / Linux

```bash
cp .env.example .env
```

# Windows

```powershell
Copy-Item .env.example .env
```

## 4. Write env keys

# Github Token
1. Create GitHub account or log in
2. Go to Settings → Developer settings (bottom) → Personal access tokens → Fine-grained tokens.
3. Generate token.

```bash
echo 'GITHUB_TOKEN=your_token_here >> .env
```

## 5. Run project

### Pipeline

<img width="1672" height="941" alt="Recruitment Agency Pipeline" src="https://github.com/user-attachments/assets/ec9ccb49-74f8-45ed-b586-451c2532d201" />
