MediScan AI 🩺🤖

MediScan AI is an AI-powered medical report analysis web application
designed to turn uploaded medical reports into structured,
easy-to-understand insights.

⚠️ Medical Disclaimer: MediScan AI is an informational tool and is
not a substitute for a qualified healthcare professional. AI-generated
results may be incomplete or incorrect and should not be used as a
diagnosis or as the sole basis for medical decisions.

✨ Features

📄 Upload and process medical reports

🔎 Extract report information for analysis

🤖 AI-powered analysis using Groq

📊 Structured results including summary, risk level, risk score,
parameters, conditions, alerts, recommendations, lifestyle advice,
and follow-up

🧠 Rule-based fallback analysis when AI analysis is unavailable

📱 Responsive web interface

📥 PDF, PNG, and JPG report downloads

📱 QR-code based report sharing/download

🌐 Temporary public access through ngrok during development

🔐 Backend environment variables for API credentials

🛠️ Technology Stack

Frontend

HTML5

CSS3

JavaScript

Responsive UI

DM Sans / DM Serif Display

Backend

Python

Flask

AI

Groq API

Structured JSON AI responses

Rule-based fallback analysis

Development

Git

GitHub

ngrok

📁 Project Structure

MediScan_AI_V3/
├── app.py
├── ai_engine.py
├── templates/
│ └── download_page.html
├── static/
│ ├── css/
│ │ └── style.css
│ └── ...
├── .env
├── .gitignore
└── README.md

Generated reports, uploaded files, and secrets should not be committed
to GitHub.

🚀 Installation

1. Clone the repository

git clone https://github.com/gnanendra714/MediScan-AI.git
cd MediScan-AI

2. Create a virtual environment

Windows:

python -m venv venv
venv\Scripts\activate

macOS/Linux:

python3 -m venv venv
source venv/bin/activate

3. Install dependencies

pip install -r requirements.txt

If requirements.txt is not present yet, install the packages required
by the current project, including Flask, Groq, python-dotenv, and its
OCR/report-processing dependencies.

🔐 Environment Configuration

Create a .env file in the project root:

GROQ_API_KEY=your_groq_api_key
PUBLIC_URL=http://localhost:5000

For development with ngrok:

GROQ_API_KEY=your_groq_api_key
PUBLIC_URL=https://your-ngrok-url.ngrok-free.app

Never commit .env or API keys to GitHub.

▶️ Run MediScan AI

Start Flask:

python app.py

Open:

http://localhost:5000

🌐 Public QR Access with ngrok

For development/demo testing:

python app.py

In another terminal:

ngrok http 5000

ngrok provides an HTTPS URL similar to:

https://example.ngrok-free.app

Set that URL as PUBLIC_URL in .env and restart Flask.

The QR code then points to a public report URL such as:

https://example.ngrok-free.app/download_page/<report_name>

Flask renders the project's templates/download_page.html page for that
route.

ngrok temporary tunnels are intended for development/testing.
Production deployment should use a proper hosted backend and
persistent public URL.

📥 Report Download Flow

Medical Report
↓
MediScan AI
↓
AI / Rule-Based Analysis
↓
Generated Report
↓
QR Code
↓
Public Download URL
↓
download_page.html
↓
PDF / PNG / JPG

The QR code contains a web URL, not a Windows filesystem path.

🧠 AI Analysis

MediScan AI requests structured AI output covering:

Summary

Risk level

Risk score

Parameters

Conditions identified

Critical alerts

Recommendations

Lifestyle advice

Follow-up

Disclaimer

When the AI service is unavailable, the application can use its
rule-based fallback analysis.

🔐 Security

Never commit:

.env
API keys
uploaded medical reports
generated patient reports
private user data

Recommended .gitignore entries:

.env
**pycache**/
_.pyc
venv/
.venv/
uploads/
reports/
_.pdf
_.png
_.jpg
\*.jpeg

If an API key is exposed, revoke/rotate it immediately.

⚠️ Medical Safety

MediScan AI is a supporting information tool and should not:

Replace a doctor or qualified healthcare professional

Provide a definitive diagnosis

Be used as the sole basis for treatment decisions

Replace emergency medical care

Encourage users to ignore professional medical advice

Users should consult an appropriate healthcare professional for
interpretation of medical results and treatment decisions.

🔮 Future Improvements

Production cloud deployment

Persistent public URLs

User authentication

Secure cloud storage

Database-backed report history

Improved OCR and medical document parsing

Multilingual explanations

Accessibility improvements

Privacy controls

Production monitoring and error tracking

👨‍💻 Author

Gnanendra

MediScan AI --- AI-powered medical report analysis and report sharing
platform.

📄 License

Add an appropriate open-source license before publishing the repository
publicly. If you choose MIT, add a LICENSE file containing the
official MIT License text.
