import os
import re
import sys
import io
import base64
import socket
import tempfile
from datetime import datetime

from flask import Flask, render_template, request, jsonify, send_file, abort
from flask_cors import CORS
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from ai_engine import analyze_with_ai
from report_generator import generate_pdf_report, generate_image_report


# ─────────────────────────────────────────────────────────────────────────────
# ENVIRONMENT
# ─────────────────────────────────────────────────────────────────────────────

load_dotenv()


# ─────────────────────────────────────────────────────────────────────────────
# FLASK APP
# ─────────────────────────────────────────────────────────────────────────────

app = Flask(__name__)

CORS(app)

app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024


# ─────────────────────────────────────────────────────────────────────────────
# STORAGE
#
# Local Windows:
#     Uses the system temporary directory.
#
# Vercel:
#     Uses /tmp automatically.
#
# This avoids writing into the read-only deployed project directory.
# ─────────────────────────────────────────────────────────────────────────────

TEMP_ROOT = tempfile.gettempdir()

app.config["UPLOAD_FOLDER"] = os.path.join(
    TEMP_ROOT,
    "mediscan_uploads"
)

app.config["REPORTS_FOLDER"] = os.path.join(
    TEMP_ROOT,
    "mediscan_reports"
)

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["REPORTS_FOLDER"], exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# ALLOWED FILES
# ─────────────────────────────────────────────────────────────────────────────

ALLOWED_EXTENSIONS = {
    "pdf",
    "txt",
    "docx",
    "png",
    "jpg",
    "jpeg"
}


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


# ─────────────────────────────────────────────────────────────────────────────
# LOCAL NETWORK IP
# Used only when running locally.
# ─────────────────────────────────────────────────────────────────────────────

def get_lan_ip():
    """Get the real LAN IP for local-network access."""

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip

    except Exception:
        return "127.0.0.1"


# ─────────────────────────────────────────────────────────────────────────────
# TEXT EXTRACTION — IMAGE / OCR
# ─────────────────────────────────────────────────────────────────────────────

def extract_text_from_image(filepath):
    """
    OCR with preprocessing.

    Works locally when Tesseract is installed.
    On environments without Tesseract, returns a helpful message.
    """

    try:
        from PIL import Image, ImageEnhance, ImageFilter, ImageOps
        import pytesseract

        # Windows Tesseract auto-detection
        if sys.platform == "win32":

            candidates = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                r"C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe".format(
                    os.getenv("USERNAME", "")
                ),
            ]

            for candidate in candidates:

                if os.path.exists(candidate):
                    pytesseract.pytesseract.tesseract_cmd = candidate
                    break

        img = Image.open(filepath).convert("RGB")

        results = []

        def try_ocr(image, config):

            try:
                return pytesseract.image_to_string(
                    image,
                    config=config
                ).strip()

            except Exception:
                return ""

        # ─────────────────────────────────────────────────────────────────────
        # Image enhancement
        # ─────────────────────────────────────────────────────────────────────

        def enhance(image):

            if image.width < 1200:

                image = image.resize(
                    (
                        image.width * 2,
                        image.height * 2
                    ),
                    Image.LANCZOS
                )

            image = image.convert("L")

            image = ImageOps.autocontrast(
                image,
                cutoff=2
            )

            image = ImageEnhance.Sharpness(
                image
            ).enhance(2.0)

            image = ImageEnhance.Contrast(
                image
            ).enhance(1.8)

            return image

        configs = [
            "--psm 6 --oem 3",
            "--psm 4 --oem 3",
            "--psm 3 --oem 3",
            "--psm 6 --oem 1",
        ]

        enhanced = enhance(img.copy())

        # OCR enhanced versions
        for config in configs:

            text = try_ocr(
                enhanced,
                config
            )

            results.append(text)

        # OCR original image
        for config in configs[:2]:

            text = try_ocr(
                img,
                config
            )

            results.append(text)

        best = max(
            results,
            key=lambda x: len(x)
        )

        return (
            best
            if best
            else "[No text extracted — please paste report text manually]"
        )

    except ImportError:

        return (
            "[OCR unavailable: install pytesseract + Pillow, "
            "and Tesseract binary]\n"
            "Please paste the report text manually."
        )

    except Exception as e:

        return (
            f"[Image OCR error: {e}]\n"
            "Please paste the report text manually."
        )


# ─────────────────────────────────────────────────────────────────────────────
# TEXT EXTRACTION — PDF / DOCX / TXT / IMAGE
# ─────────────────────────────────────────────────────────────────────────────

def extract_text_from_file(filepath, filename):

    ext = filename.rsplit(".", 1)[1].lower()

    text = ""

    try:

        # ─────────────────────────────────────────────────────────────────────
        # PDF
        # ─────────────────────────────────────────────────────────────────────

        if ext == "pdf":

            import pdfplumber

            with pdfplumber.open(filepath) as pdf:

                for page in pdf.pages:

                    page_text = page.extract_text()

                    if page_text:
                        text += page_text + "\n"

            # Fallback PDF parser
            if not text.strip():

                import PyPDF2

                with open(filepath, "rb") as f:

                    reader = PyPDF2.PdfReader(f)

                    for page in reader.pages:

                        page_text = page.extract_text()

                        if page_text:
                            text += page_text + "\n"

        # ─────────────────────────────────────────────────────────────────────
        # DOCX
        # ─────────────────────────────────────────────────────────────────────

        elif ext == "docx":

            import docx as docxlib

            doc = docxlib.Document(filepath)

            for paragraph in doc.paragraphs:

                text += paragraph.text + "\n"

        # ─────────────────────────────────────────────────────────────────────
        # TXT
        # ─────────────────────────────────────────────────────────────────────

        elif ext == "txt":

            with open(
                filepath,
                "r",
                encoding="utf-8",
                errors="ignore"
            ) as f:

                text = f.read()

        # ─────────────────────────────────────────────────────────────────────
        # IMAGE
        # ─────────────────────────────────────────────────────────────────────

        elif ext in (
            "png",
            "jpg",
            "jpeg"
        ):

            text = extract_text_from_image(filepath)

    except Exception as e:

        text = f"Error extracting text: {e}"

    return text.strip()


# ─────────────────────────────────────────────────────────────────────────────
# PATIENT INFORMATION
# ─────────────────────────────────────────────────────────────────────────────

def extract_patient_info(text):

    name = "Unknown"
    age = "Unknown"
    gender = "Unknown"

    flat = text.replace(
        "\n",
        " "
    ).strip()

    # Patient name
    name_match = re.search(
        r"Patient[\s\w]*[Nn]ame\s*[:\-]?\s*([A-Za-z .]{3,40})",
        flat,
        re.IGNORECASE
    )

    if name_match:

        name = name_match.group(1).strip()

    # Title-based name
    if name == "Unknown":

        title_match = re.search(
            r"(Mr\.?|Mrs\.?|Ms\.?|Dr\.?)\s+([A-Za-z ]{3,30})",
            flat
        )

        if title_match:

            name = (
                title_match.group(1)
                + " "
                + title_match.group(2)
            ).strip()

    # First words fallback
    if name == "Unknown":

        words = flat.split()

        candidate = " ".join(
            words[:3]
        )

        if re.match(
            r"[A-Za-z]+\s+[A-Za-z]+",
            candidate
        ):

            name = candidate

    # Age
    age_match = re.search(
        r"\bAge\s*[:/\-]?\s*(\d{1,3})",
        flat,
        re.IGNORECASE
    )

    if age_match:

        age = age_match.group(1)

    # Gender
    gender_match = re.search(
        r"(?:Sex|Gender)\s*[:/\-]?\s*(Male|Female|M\b|F\b)",
        flat,
        re.IGNORECASE
    )

    if gender_match:

        gender_value = gender_match.group(1).upper()

        gender = (
            "Male"
            if gender_value in ("M", "MALE")
            else "Female"
        )

    return name, age, gender


# ─────────────────────────────────────────────────────────────────────────────
# QR CODE
# ─────────────────────────────────────────────────────────────────────────────

def make_qr_data_url(url):

    try:

        import qrcode
        from io import BytesIO

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=6,
            border=3
        )

        qr.add_data(url)

        qr.make(
            fit=True
        )

        img = qr.make_image(
            fill_color="black",
            back_color="white"
        )

        buffer = BytesIO()

        img.save(
            buffer,
            format="PNG"
        )

        encoded = base64.b64encode(
            buffer.getvalue()
        ).decode()

        return (
            "data:image/png;base64,"
            + encoded
        )

    except ImportError:

        return ""

    except Exception:

        return ""


# ─────────────────────────────────────────────────────────────────────────────
# HOME
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():

    return render_template(
        "index.html"
    )


# ─────────────────────────────────────────────────────────────────────────────
# ANALYZE
# ─────────────────────────────────────────────────────────────────────────────

@app.route(
    "/analyze",
    methods=["POST"]
)
def analyze():

    report_text = ""

    filename = "Manual Input"

    extracted_preview = ""

    # ─────────────────────────────────────────────────────────────────────────
    # FILE UPLOAD
    # ─────────────────────────────────────────────────────────────────────────

    if (
        "file" in request.files
        and request.files["file"].filename
    ):

        file = request.files["file"]

        if file and allowed_file(file.filename):

            filename = secure_filename(
                file.filename
            )

            filepath = os.path.join(
                app.config["UPLOAD_FOLDER"],
                filename
            )

            file.save(filepath)

            report_text = extract_text_from_file(
                filepath,
                filename
            )

            extracted_preview = report_text[:400]

    # ─────────────────────────────────────────────────────────────────────────
    # MANUAL TEXT
    # ─────────────────────────────────────────────────────────────────────────

    if (
        not report_text
        and "report_text" in request.form
    ):

        report_text = request.form[
            "report_text"
        ].strip()

    # ─────────────────────────────────────────────────────────────────────────
    # VALIDATION
    # ─────────────────────────────────────────────────────────────────────────

    if not report_text:

        return jsonify({
            "error": "No medical report content provided"
        }), 400

    # ─────────────────────────────────────────────────────────────────────────
    # PATIENT INFO
    # ─────────────────────────────────────────────────────────────────────────

    (
        patient_name,
        patient_age,
        patient_gender
    ) = extract_patient_info(
        report_text
    )

    # ─────────────────────────────────────────────────────────────────────────
    # AI ANALYSIS
    # ─────────────────────────────────────────────────────────────────────────

    result = analyze_with_ai(
        report_text,
        patient_name,
        patient_age,
        patient_gender
    )

    # ─────────────────────────────────────────────────────────────────────────
    # REPORT NAME
    # ─────────────────────────────────────────────────────────────────────────

    ts = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    base_name = (
        f"mediscan_report_{ts}"
    )

    # ─────────────────────────────────────────────────────────────────────────
    # PDF REPORT
    # ─────────────────────────────────────────────────────────────────────────

    pdf_file = (
        base_name
        + ".pdf"
    )

    pdf_path = os.path.join(
        app.config["REPORTS_FOLDER"],
        pdf_file
    )

    try:

        generate_pdf_report(
            result,
            patient_name,
            patient_age,
            patient_gender,
            pdf_path,
            filename
        )

        result["report_file"] = pdf_file

    except Exception as e:

        result["report_file"] = None

        result["pdf_error"] = str(e)

    # ─────────────────────────────────────────────────────────────────────────
    # PNG REPORT
    # ─────────────────────────────────────────────────────────────────────────

    png_file = (
        base_name
        + ".png"
    )

    png_path = os.path.join(
        app.config["REPORTS_FOLDER"],
        png_file
    )

    try:

        generate_image_report(
            result,
            patient_name,
            patient_age,
            patient_gender,
            png_path,
            fmt="PNG"
        )

        result["report_png"] = png_file

    except Exception:

        result["report_png"] = None

    # ─────────────────────────────────────────────────────────────────────────
    # JPG REPORT
    # ─────────────────────────────────────────────────────────────────────────

    jpg_file = (
        base_name
        + ".jpg"
    )

    jpg_path = os.path.join(
        app.config["REPORTS_FOLDER"],
        jpg_file
    )

    try:

        generate_image_report(
            result,
            patient_name,
            patient_age,
            patient_gender,
            jpg_path,
            fmt="JPEG"
        )

        result["report_jpg"] = jpg_file

    except Exception:

        result["report_jpg"] = None

    # ─────────────────────────────────────────────────────────────────────────
    # RESULT METADATA
    # ─────────────────────────────────────────────────────────────────────────

    result["report_base"] = base_name

    result["patient_name"] = patient_name

    result["patient_age"] = patient_age

    result["patient_gender"] = patient_gender

    result["extracted_preview"] = extracted_preview

    # ─────────────────────────────────────────────────────────────────────────
    # PUBLIC URL / QR
    #
    # Local + ngrok:
    # PUBLIC_URL=https://xxxx.ngrok-free.dev
    #
    # Vercel:
    # PUBLIC_URL=https://mediscan-ai.vercel.app
    #
    # If PUBLIC_URL isn't configured, Flask automatically uses
    # the current request host.
    # ─────────────────────────────────────────────────────────────────────────

    public_url = os.getenv(
        "PUBLIC_URL",
        ""
    ).strip().rstrip("/")

    if not public_url:

        public_url = (
            request.host_url
            .rstrip("/")
        )

    download_url = (
        f"{public_url}"
        f"/download_page/{base_name}"
    )

    result["qr_code"] = (
        make_qr_data_url(
            download_url
        )
    )

    result["download_url"] = (
        download_url
    )

    return jsonify(result)


# ─────────────────────────────────────────────────────────────────────────────
# DOWNLOAD PAGE
# ─────────────────────────────────────────────────────────────────────────────

@app.route(
    "/download_page/<base_name>"
)
def download_page(base_name):

    if not re.match(
        r"^mediscan_report_\d{8}_\d{6}$",
        base_name
    ):

        abort(404)

    files = {}

    for ext in (
        "pdf",
        "png",
        "jpg"
    ):

        path = os.path.join(
            app.config["REPORTS_FOLDER"],
            f"{base_name}.{ext}"
        )

        if os.path.exists(path):

            files[ext] = (
                f"{base_name}.{ext}"
            )

    return render_template(
        "download_page.html",
        base_name=base_name,
        files=files
    )


# ─────────────────────────────────────────────────────────────────────────────
# DOWNLOAD REPORT
# ─────────────────────────────────────────────────────────────────────────────

@app.route(
    "/download/<filename>"
)
def download_report(filename):

    filename = secure_filename(
        filename
    )

    path = os.path.join(
        app.config["REPORTS_FOLDER"],
        filename
    )

    if not os.path.exists(path):

        return jsonify({
            "error": "File not found"
        }), 404

    ext = filename.rsplit(
        ".",
        1
    )[-1].lower()

    mime_map = {
        "pdf": "application/pdf",
        "png": "image/png",
        "jpg": "image/jpeg"
    }

    return send_file(
        path,
        as_attachment=True,
        mimetype=mime_map.get(
            ext,
            "application/octet-stream"
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
# SAMPLE REPORT
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/sample")
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

    return jsonify({
        "sample": sample
    })


# ─────────────────────────────────────────────────────────────────────────────
# LOCAL DEVELOPMENT SERVER
#
# This section runs ONLY when:
#
#     python app.py
#
# Vercel does not execute this section as the web server.
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    port = int(
        os.getenv(
            "PORT",
            5000
        )
    )

    lan_ip = get_lan_ip()

    public_url = os.getenv(
        "PUBLIC_URL",
        ""
    ).strip().rstrip("/")

    print()
    print("🏥 MediScan AI is running!")
    print(
        f"   Local:   http://localhost:{port}"
    )
    print(
        f"   Network: http://{lan_ip}:{port}"
    )

    if public_url:

        print(
            f"   Public:  {public_url}"
        )

        print(
            "   QR:      QR codes will use "
            "the configured PUBLIC_URL"
        )

    else:

        print(
            "   Public:  NOT CONFIGURED"
        )

        print(
            "   QR:      Using the current "
            "request URL as fallback"
        )

        print(
            "   Add PUBLIC_URL to .env for "
            "internet-accessible QR codes"
        )

    print()

    app.run(
        host="0.0.0.0",
        port=port
    )