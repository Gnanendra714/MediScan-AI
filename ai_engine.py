"""
AI Engine for MediScan AI
Groq AI support with rule-based fallback
"""

import os
import re
import json
import time
from dotenv import load_dotenv

from groq import Groq

# ─── ENVIRONMENT / API KEYS ──────────────────────────────────────────────────
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """You are MediScan AI, an expert medical report analysis system. 
Analyze the given medical report and return a structured JSON response with the following fields:

{
  "summary": "2-3 sentence overall health summary",
  "risk_level": "Normal | Needs Attention | Critical",
  "risk_score": 0-100,
  "parameters": [
    {
      "name": "Parameter name",
      "value": "Patient value with unit",
      "normal_range": "Normal range",
      "status": "Normal | Low | High | Critical Low | Critical High",
      "interpretation": "Brief clinical interpretation"
    }
  ],
  "conditions_identified": [
    {
      "condition": "Condition name",
      "confidence": "High | Moderate | Low",
      "evidence": "Which parameters suggest this"
    }
  ],
  "critical_alerts": ["List of urgent findings requiring immediate attention"],
  "recommendations": [
    {
      "priority": "Urgent | High | Medium | Low",
      "action": "Specific recommendation"
    }
  ],
  "lifestyle_advice": ["List of lifestyle modification suggestions"],
  "followup": "Suggested follow-up timeline and tests",
  "disclaimer": "Always include: This analysis is AI-generated and should not replace professional medical advice. Please consult a qualified healthcare provider."
}

Be thorough, clinically accurate, and compassionate. Always identify ALL abnormal values."""

USER_PROMPT_TEMPLATE = """
Patient Information:
- Name: {name}
- Age: {age}
- Gender: {gender}

Medical Report Content:
{report_text}

Analyze this complete medical report and return ONLY valid JSON with no extra text.
"""


def call_groq(report_text: str, name: str, age: str, gender: str) -> dict:
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set")

    client = Groq(api_key=GROQ_API_KEY)

    models = [
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b"
    ]

    for model in models:
        try:
            print(f"[MediScan] Trying Groq model: {model}")

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": USER_PROMPT_TEMPLATE.format(
                        name=name,
                        age=age,
                        gender=gender,
                        report_text=report_text[:6000]
                    )}
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content

            import re, json
            match = re.search(r'\{[\s\S]*\}', content)
            if match:
                result = json.loads(match.group())
                result["ai_provider"] = f"Groq ({model})"
                print("[MediScan] Groq analysis successful")
                return result

        except Exception as e:
            print(f"[MediScan] Model {model} failed:", e)

    raise Exception("All Groq models failed")

def rule_based_analysis(report_text: str, name: str, age: str, gender: str) -> dict:
    """
    Rule-based fallback analyzer - no API key required.
    Detects common abnormal values using regex patterns.
    """
    text = report_text.upper()
    parameters = []
    conditions = []
    alerts = []
    recommendations = []
    risk_score = 0

    # ── Pattern definitions ────────────────────────────────────────────────
    checks = [
        # (regex pattern, param name, unit, low_thresh, high_thresh, normal_range)
        (r'HEMOGLOBIN[:\s]+(\d+\.?\d*)', 'Hemoglobin', 'g/dL', 8, 17.5, '13.5-17.5 g/dL (M) / 12-15.5 g/dL (F)'),
        (r'WBC[:\s]+(\d+[,\d]*)', 'WBC Count', '/µL', 4000, 11000, '4,500-11,000 /µL'),
        (r'GLUCOSE[:\s]+(\d+\.?\d*)', 'Glucose', 'mg/dL', 70, 100, '70-100 mg/dL (fasting)'),
        (r'HBA1C[:\s]+(\d+\.?\d*)', 'HbA1c', '%', 0, 5.7, 'Below 5.7%'),
        (r'CREATININE[:\s]+(\d+\.?\d*)', 'Creatinine', 'mg/dL', 0.5, 1.2, '0.6-1.2 mg/dL'),
        (r'TOTAL CHOLESTEROL[:\s]+(\d+\.?\d*)', 'Total Cholesterol', 'mg/dL', 0, 200, 'Below 200 mg/dL'),
        (r'LDL[:\s]+(\d+\.?\d*)', 'LDL Cholesterol', 'mg/dL', 0, 100, 'Below 100 mg/dL'),
        (r'TRIGLYCERIDES[:\s]+(\d+\.?\d*)', 'Triglycerides', 'mg/dL', 0, 150, 'Below 150 mg/dL'),
        (r'TSH[:\s]+(\d+\.?\d*)', 'TSH', 'mIU/L', 0.4, 4.0, '0.4-4.0 mIU/L'),
        (r'PLATELET[:\s]+(\d+[,\d]*)', 'Platelet Count', '/µL', 150000, 400000, '150,000-400,000 /µL'),
        (r'AST[:\s]+(\d+\.?\d*)', 'AST', 'U/L', 0, 40, '10-40 U/L'),
        (r'ALT[:\s]+(\d+\.?\d*)', 'ALT', 'U/L', 0, 56, '7-56 U/L'),
        (r'BUN[:\s]+(\d+\.?\d*)', 'BUN', 'mg/dL', 0, 25, '7-25 mg/dL'),
        (r'HDL[:\s]+(\d+\.?\d*)', 'HDL Cholesterol', 'mg/dL', 40, 999, 'Above 40 mg/dL'),
    ]

    for pattern, param_name, unit, low, high, normal_range in checks:
        match = re.search(pattern, text)
        if match:
            try:
                val_str = match.group(1).replace(',', '')
                val = float(val_str)
                if val < low:
                    status = 'Critical Low' if val < low * 0.7 else 'Low'
                    risk_score += 20 if 'Critical' in status else 10
                elif val > high:
                    status = 'Critical High' if val > high * 1.5 else 'High'
                    risk_score += 20 if 'Critical' in status else 10
                else:
                    status = 'Normal'

                parameters.append({
                    'name': param_name,
                    'value': f"{val} {unit}",
                    'normal_range': normal_range,
                    'status': status,
                    'interpretation': _interpret_param(param_name, val, status)
                })
                if 'Critical' in status:
                    alerts.append(f"{param_name} is {status}: {val} {unit}")
            except:
                pass

    # Blood pressure
    bp_match = re.search(r'BLOOD PRESSURE[:\s]+(\d+)/(\d+)', text)
    if bp_match:
        systolic, diastolic = int(bp_match.group(1)), int(bp_match.group(2))
        if systolic >= 140 or diastolic >= 90:
            status = 'Critical High' if systolic >= 180 else 'High'
            risk_score += 20 if 'Critical' in status else 10
        else:
            status = 'Normal'
        parameters.append({
            'name': 'Blood Pressure',
            'value': f"{systolic}/{diastolic} mmHg",
            'normal_range': 'Below 120/80 mmHg',
            'status': status,
            'interpretation': _interpret_param('Blood Pressure', systolic, status)
        })
        if 'Critical' in status:
            alerts.append(f"Blood Pressure is critically elevated: {systolic}/{diastolic} mmHg")

    # Detect conditions
    abnormal = [p for p in parameters if p['status'] != 'Normal']
    param_names = [p['name'] for p in abnormal]

    if 'HbA1c' in param_names or 'Glucose' in param_names:
        conditions.append({'condition': 'Possible Diabetes / Pre-diabetes', 'confidence': 'High', 'evidence': 'Elevated HbA1c and/or fasting glucose'})
        recommendations.append({'priority': 'High', 'action': 'Consult endocrinologist. Start diabetic diet and consider medication.'})

    if 'Hemoglobin' in param_names and any(p['name'] == 'Hemoglobin' and 'Low' in p['status'] for p in parameters):
        conditions.append({'condition': 'Anemia', 'confidence': 'High', 'evidence': 'Low hemoglobin levels'})
        recommendations.append({'priority': 'High', 'action': 'Investigate cause of anemia. Check iron studies and B12.'})

    if any(n in param_names for n in ['Total Cholesterol', 'LDL Cholesterol', 'Triglycerides']):
        conditions.append({'condition': 'Dyslipidemia', 'confidence': 'Moderate', 'evidence': 'Elevated cholesterol/triglycerides'})
        recommendations.append({'priority': 'Medium', 'action': 'Diet modification, exercise. Consider statin therapy.'})

    if 'Creatinine' in param_names or 'BUN' in param_names:
        conditions.append({'condition': 'Possible Renal Impairment', 'confidence': 'Moderate', 'evidence': 'Elevated creatinine or BUN'})
        recommendations.append({'priority': 'High', 'action': 'Nephrology consult. Monitor kidney function. Avoid nephrotoxic drugs.'})

    if 'Blood Pressure' in param_names:
        conditions.append({'condition': 'Hypertension', 'confidence': 'High', 'evidence': 'Elevated blood pressure reading'})
        recommendations.append({'priority': 'High', 'action': 'Lifestyle changes + antihypertensive medication if persistent.'})

    risk_score = min(risk_score, 100)
    if risk_score == 0 and not parameters:
        risk_level = 'Normal'
    elif risk_score < 25:
        risk_level = 'Needs Attention'
    elif risk_score < 50:
        risk_level = 'Needs Attention'
    else:
        risk_level = 'Critical'

    if not conditions and not abnormal:
        risk_level = 'Normal'

    recommendations.append({'priority': 'Low', 'action': 'Maintain healthy diet rich in fruits, vegetables, and whole grains.'})
    recommendations.append({'priority': 'Low', 'action': 'Regular exercise: 30 minutes of moderate activity 5 days/week.'})

    return {
        'summary': f"Analysis identified {len(abnormal)} abnormal parameter(s) out of {len(parameters)} tested. "
                   f"Risk classification: {risk_level}. "
                   f"{'Immediate medical attention recommended.' if risk_level == 'Critical' else 'Please follow up with your healthcare provider.'}",
        'risk_level': risk_level,
        'risk_score': risk_score,
        'parameters': parameters,
        'conditions_identified': conditions,
        'critical_alerts': alerts,
        'recommendations': recommendations,
        'lifestyle_advice': [
            'Maintain a balanced diet low in processed foods and sugar',
            'Exercise regularly — aim for 150 minutes per week',
            'Stay hydrated: drink 8-10 glasses of water daily',
            'Avoid smoking and limit alcohol consumption',
            'Manage stress through meditation, yoga, or adequate sleep',
            'Schedule regular health check-ups every 6-12 months'
        ],
        'followup': 'Follow up with your primary care physician within 2-4 weeks. Repeat abnormal tests in 4-8 weeks.',
        'ai_provider': 'Rule-Based Analysis (No API Key)',
        'disclaimer': 'This analysis is AI-generated and should not replace professional medical advice. Please consult a qualified healthcare provider for proper diagnosis and treatment.'
    }


def _interpret_param(name: str, value: float, status: str) -> str:
    interpretations = {
        'Hemoglobin': {'Low': 'Suggests anemia — possibly iron deficiency or chronic disease', 'High': 'Polycythemia possible — dehydration or bone marrow disorder'},
        'WBC Count': {'High': 'Leukocytosis — may indicate infection or inflammation', 'Low': 'Leukopenia — immune suppression or bone marrow issue'},
        'Glucose': {'High': 'Hyperglycemia — diabetes or pre-diabetes risk', 'Low': 'Hypoglycemia — requires immediate attention'},
        'HbA1c': {'High': 'Indicates poor blood sugar control over past 3 months — diabetes risk'},
        'Creatinine': {'High': 'Elevated kidney waste marker — possible renal impairment'},
        'Total Cholesterol': {'High': 'Elevated cardiovascular risk — dietary changes needed'},
        'LDL Cholesterol': {'High': 'Bad cholesterol high — atherosclerosis risk increased'},
        'HDL Cholesterol': {'Low': 'Low protective cholesterol — cardiovascular risk factor'},
        'Triglycerides': {'High': 'Elevated fat in blood — metabolic syndrome risk'},
        'TSH': {'Low': 'Possible hyperthyroidism — overactive thyroid', 'High': 'Possible hypothyroidism — underactive thyroid'},
        'Blood Pressure': {'High': 'Hypertension — increases risk of heart disease and stroke'},
        'Platelet Count': {'Low': 'Thrombocytopenia — bleeding risk increased', 'High': 'Thrombocytosis — clotting risk'},
        'AST': {'High': 'Elevated liver enzyme — liver stress or damage'},
        'ALT': {'High': 'Elevated liver enzyme — hepatic inflammation possible'},
        'BUN': {'High': 'Elevated blood urea — possible kidney dysfunction'},
    }
    param_interp = interpretations.get(name, {})
    for key in ['Critical High', 'High', 'Critical Low', 'Low']:
        if key in status and key in param_interp:
            return param_interp[key]
        if 'High' in status and 'High' in param_interp:
            return param_interp['High']
        if 'Low' in status and 'Low' in param_interp:
            return param_interp['Low']
    return 'Within acceptable range — continue monitoring'


def analyze_with_ai(report_text: str, name: str = 'Patient', age: str = 'Unknown', gender: str = 'Unknown') -> dict:
    """
    Main analysis function with fallback chain:
    Groq → Rule-Based
    """
    providers_tried = []

    # Try Groq first
    if GROQ_API_KEY:
        try:
            print("[MediScan] Trying Groq API...")
            result = call_groq(report_text, name, age, gender)
            result['ai_provider'] = result.get('ai_provider', 'Groq')
            if 'disclaimer' not in result:
                result['disclaimer'] = 'This analysis is AI-generated and should not replace professional medical advice. Please consult a qualified healthcare provider.'
            print("[MediScan] Groq analysis successful")
            return result
        except Exception as e:
            providers_tried.append(f"Groq: {str(e)[:100]}")
            print(f"[MediScan] Groq failed: {e}")

    # Final fallback: rule-based
    print("[MediScan] Using rule-based analysis fallback")
    result = rule_based_analysis(report_text, name, age, gender)
    if providers_tried:
        result['providers_tried'] = providers_tried
    return result
