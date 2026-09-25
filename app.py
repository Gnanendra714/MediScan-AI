import os, re, sys, io, base64, socket
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, abort
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from ai_engine import analyze_with_ai
from report_generator import generate_pdf_report, generate_image_report
from flask import request

load_dotenv()

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024
app.config['UPLOAD_FOLDER']  = 'uploads'
app.config['REPORTS_FOLDER'] = 'reports'

ALLOWED_EXTENSIONS = {'pdf', 'txt', 'docx', 'png', 'jpg', 'jpeg'}

os.makedirs('uploads',  exist_ok=True)
os.makedirs('reports',  exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_lan_ip():
    """Get the real LAN IP so QR works on any device on the same network."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


# ── Text extraction ──────────────────────────────────────────────────────────

def extract_text_from_image(filepath):
    """OCR with preprocessing — best effort for medical report images."""
    try:
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps
        import pytesseract

        # Windows Tesseract path (auto-detect)
        if sys.platform == 'win32':
            candidates = [
                r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
                r'C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'.format(os.getenv('USERNAME','')),
            ]
            for c in candidates:
                if os.path.exists(c):
                    pytesseract.pytesseract.tesseract_cmd = c
                    break

        img = Image.open(filepath).convert('RGB')
        w, h = img.size

        results = []

        def try_ocr(im, cfg):
            try:
                return pytesseract.image_to_string(im, config=cfg).strip()
            except Exception:
                return ''

        # Preprocess variants
        def enhance(im):
            if im.width < 1200:
                im = im.resize((im.width * 2, im.height * 2), Image.LANCZOS)
            im = im.convert('L')
            im = ImageOps.autocontrast(im, cutoff=2)
            im = ImageEnhance.Sharpness(im).enhance(2.0)
            im = ImageEnhance.Contrast(im).enhance(1.8)
            return im

        configs = [
            '--psm 6 --oem 3',
            '--psm 4 --oem 3',
            '--psm 3 --oem 3',
            '--psm 6 --oem 1',
        ]

        enhanced = enhance(img.copy())
        for cfg in configs:
            t = try_ocr(enhanced, cfg)
            results.append(t)

        # Also try original
        for cfg in configs[:2]:
            t = try_ocr(img, cfg)
            results.append(t)

        best = max(results, key=lambda x: len(x))
        return best if best else '[No text extracted — please paste report text manually]'

    except ImportError:
        return '[OCR unavailable: install pytesseract + Pillow, and Tesseract binary]\nPlease paste report text manually.'
    except Exception as e:
        return f'[Image OCR error: {e}]\nPlease paste report text manually.'


def extract_text_from_file(filepath, filename):
    ext = filename.rsplit('.', 1)[1].lower()
    text = ''
    try:
        if ext == 'pdf':
            import pdfplumber
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text += t + '\n'
            if not text.strip():
                import PyPDF2
                with open(filepath, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        t = page.extract_text()
                        if t:
                            text += t + '\n'
        elif ext == 'docx':
            import docx as docxlib
            doc = docxlib.Document(filepath)
            for para in doc.paragraphs:
                text += para.text + '\n'
        elif ext == 'txt':
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
        elif ext in ('png', 'jpg', 'jpeg'):
            text = extract_text_from_image(filepath)
    except Exception as e:
        text = f'Error extracting text: {e}'
    return text.strip()


def extract_patient_info(text):
    name = 'Unknown'; age = 'Unknown'; gender = 'Unknown'
    flat = text.replace('\n', ' ').strip()
    nm = re.search(r'Patient[\s\w]*[Nn]ame\s*[:\-]?\s*([A-Za-z .]{3,40})', flat, re.IGNORECASE)
    if nm: name = nm.group(1).strip()
    if name == 'Unknown':
        tm = re.search(r'(Mr\.?|Mrs\.?|Ms\.?|Dr\.?)\s+([A-Za-z ]{3,30})', flat)
        if tm: name = (tm.group(1) + ' ' + tm.group(2)).strip()
    if name == 'Unknown':
        words = flat.split()
        cand = ' '.join(words[:3])
        if re.match(r'[A-Za-z]+\s+[A-Za-z]+', cand): name = cand
    am = re.search(r'\bAge\s*[:/\-]?\s*(\d{1,3})', flat, re.IGNORECASE)
    if am: age = am.group(1)
    gm = re.search(r'(?:Sex|Gender)\s*[:/\-]?\s*(Male|Female|M\b|F\b)', flat, re.IGNORECASE)
    if gm:
        g = gm.group(1).upper()
        gender = 'Male' if g in ('M','MALE') else 'Female'
    return name, age, gender


def make_qr_data_url(url: str) -> str:
    try:
        import qrcode
        from io import BytesIO
        qr = qrcode.QRCode(version=None,
                           error_correction=qrcode.constants.ERROR_CORRECT_M,
                           box_size=6, border=3)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        buf = BytesIO()
        img.save(buf, format='PNG')
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f'data:image/png;base64,{b64}'
    except ImportError:
        return ''
    except Exception:
        return ''


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    report_text = ''
    filename = 'Manual Input'
    extracted_preview = ''

    if 'file' in request.files and request.files['file'].filename:
        file = request.files['file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            report_text = extract_text_from_file(filepath, filename)
            extracted_preview = report_text[:400]

    if not report_text and 'report_text' in request.form:
        report_text = request.form['report_text'].strip()

    if not report_text:
        return jsonify({'error': 'No medical report content provided'}), 400

    patient_name, patient_age, patient_gender = extract_patient_info(report_text)

    result = analyze_with_ai(report_text, patient_name, patient_age, patient_gender)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    base_name = f'mediscan_report_{ts}'

    # PDF
    pdf_file = base_name + '.pdf'
    pdf_path = os.path.join(app.config['REPORTS_FOLDER'], pdf_file)
    try:
        generate_pdf_report(result, patient_name, patient_age, patient_gender, pdf_path, filename)
        result['report_file'] = pdf_file
    except Exception as e:
        result['report_file'] = None
        result['pdf_error'] = str(e)

    # PNG
    png_file = base_name + '.png'
    png_path = os.path.join(app.config['REPORTS_FOLDER'], png_file)
    try:
        generate_image_report(result, patient_name, patient_age, patient_gender, png_path, fmt='PNG')
        result['report_png'] = png_file
    except Exception as e:
        result['report_png'] = None

    # JPG
    jpg_file = base_name + '.jpg'
    jpg_path = os.path.join(app.config['REPORTS_FOLDER'], jpg_file)
    try:
        generate_image_report(result, patient_name, patient_age, patient_gender, jpg_path, fmt='JPEG')
        result['report_jpg'] = jpg_file
    except Exception as e:
        result['report_jpg'] = None

    result['report_base'] = base_name
    result['patient_name']  = patient_name
    result['patient_age']   = patient_age
    result['patient_gender'] = patient_gender
    result['extracted_preview'] = extracted_preview

    # ── QR: always use PUBLIC_URL when configured ─────────────────────────
    # This makes the QR code work from ANY device over the internet.
    # Example:
    # PUBLIC_URL=https://your-ngrok-url.ngrok-free.dev
    public_url = os.getenv('PUBLIC_URL', '').strip().rstrip('/')

    if not public_url:
        # Local fallback only when PUBLIC_URL is not configured.
        public_url = request.host_url.rstrip('/')

    download_url = f"{public_url}/download_page/{base_name}"
    
    result['qr_code']     = make_qr_data_url(download_url)
    result['download_url'] = download_url

    return jsonify(result)


@app.route('/download_page/<base_name>')
def download_page(base_name):
    if not re.match(r'^mediscan_report_\d{8}_\d{6}$', base_name):
        abort(404)
    files = {}
    for ext in ('pdf', 'png', 'jpg'):
        p = os.path.join(app.config['REPORTS_FOLDER'], f'{base_name}.{ext}')
        if os.path.exists(p):
            files[ext] = f'{base_name}.{ext}'
    return render_template('download_page.html', base_name=base_name, files=files)


@app.route('/download/<filename>')
def download_report(filename):
    filename = secure_filename(filename)
    path = os.path.join(app.config['REPORTS_FOLDER'], filename)
    if not os.path.exists(path):
        return jsonify({'error': 'File not found'}), 404
    ext = filename.rsplit('.', 1)[-1].lower()
    mime_map = {'pdf': 'application/pdf', 'png': 'image/png', 'jpg': 'image/jpeg'}
    return send_file(path, as_attachment=True,
                     mimetype=mime_map.get(ext, 'application/octet-stream'))


@app.route('/sample')
def get_sample():
    sample = """PATIENT MEDICAL REPORT
Date: 2026-04-07
Patient Name: Rahul Sharma
Age: 28
Sex: Male

COMPLETE BLOOD COUNT (CBC)
Hemoglobin: 15.2 g/dL
WBC Count: 7200 /µL
Platelet Count: 250000 /µL
Hematocrit: 45%

BLOOD CHEMISTRY
Glucose (Fasting): 92 mg/dL
HbA1c: 5.2%
Creatinine: 0.9 mg/dL
BUN: 14 mg/dL

LIPID PROFILE
Total Cholesterol: 170 mg/dL
LDL Cholesterol: 90 mg/dL
HDL Cholesterol: 55 mg/dL
Triglycerides: 110 mg/dL

LIVER FUNCTION
AST: 22 U/L
ALT: 25 U/L
Total Bilirubin: 0.8 mg/dL

THYROID
TSH: 2.1 mIU/L

VITALS
Blood Pressure: 118/76 mmHg
Heart Rate: 72 bpm
BMI: 22.5
"""
    return jsonify({'sample': sample})


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    lan_ip = get_lan_ip()
    public_url = os.getenv('PUBLIC_URL', '').strip().rstrip('/')

    print(f'\n🏥 MediScan AI is running!')
    print(f'   Local:   http://localhost:{port}')
    print(f'   Network: http://{lan_ip}:{port}')

    if public_url:
        print(f'   Public:  {public_url}')
        print(f'   QR:      QR codes will use the public URL above\n')
    else:
        print('   Public:  NOT CONFIGURED')
        print('   QR:      Using the local request URL as fallback')
        print('   Add PUBLIC_URL to .env for internet-accessible QR codes\n')

    app.run(host='0.0.0.0', port=port)
