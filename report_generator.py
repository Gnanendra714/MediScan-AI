"""
Report Generator for MediScan AI
Generates PDF, PNG and JPG reports
"""
import os
from datetime import datetime


# ── PDF ──────────────────────────────────────────────────────────────────────

def generate_pdf_report(result, name, age, gender, output_path, source_file=''):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                         Table, TableStyle, HRFlowable)
        from reportlab.lib.enums import TA_CENTER, TA_LEFT

        doc = SimpleDocTemplate(output_path, pagesize=A4,
                                leftMargin=2*cm, rightMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)

        styles = getSampleStyleSheet()
        GREEN = colors.HexColor('#2d6a4f')
        AMBER = colors.HexColor('#b7700d')
        RED   = colors.HexColor('#c1392b')
        BLUE  = colors.HexColor('#185fa5')
        BG    = colors.HexColor('#f4f1ec')
        MUTED = colors.HexColor('#7a756e')

        def S(n, **kw):
            return ParagraphStyle(n, parent=styles['Normal'], **kw)

        h1   = S('H1',  fontSize=20, textColor=GREEN, spaceAfter=4,  fontName='Helvetica-Bold', alignment=TA_CENTER)
        sub  = S('sub', fontSize=11, textColor=MUTED, alignment=TA_CENTER, spaceAfter=6)
        h2   = S('H2',  fontSize=13, textColor=GREEN, spaceAfter=6,  fontName='Helvetica-Bold', spaceBefore=14)
        body = S('Bd',  fontSize=10, leading=16, spaceAfter=4)
        sm   = S('Sm',  fontSize=9,  textColor=MUTED, leading=14)
        disc = S('Dc',  fontSize=9,  textColor=BLUE, leading=14,
                 backColor=colors.HexColor('#e8f0fb'),
                 borderPadding=(6,8,6,8))
        tc   = S('Tc',  fontSize=9,  leading=13)
        tc8  = S('Tc8', fontSize=8,  leading=12, textColor=MUTED)

        story = []

        story.append(Paragraph('🏥 MediScan AI', h1))
        story.append(Paragraph('AI-Powered Medical Report Analysis', sub))
        story.append(Spacer(1, 8))
        story.append(HRFlowable(width='100%', color=GREEN, thickness=1.5))
        story.append(Spacer(1, 8))

        risk_level = result.get('risk_level', 'Unknown')
        risk_color = GREEN if risk_level == 'Normal' else (AMBER if 'Attention' in risk_level else RED)

        info_data = [
            ['Patient', name,        'Age',    age,                         'Gender', gender],
            ['Risk',    Paragraph(f'<font color="{risk_color.hexval()}"><b>{risk_level}</b></font>', body),
             'Score',   str(result.get('risk_score','—')),
             'Date',    datetime.now().strftime('%d %b %Y')],
            ['Source',  source_file or 'Manual', 'Provider', result.get('ai_provider','—'), '', ''],
        ]
        it = Table(info_data, colWidths=[2.2*cm,4.2*cm,1.8*cm,2.5*cm,2*cm,3.3*cm])
        it.setStyle(TableStyle([
            ('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),
            ('FONTNAME',(2,0),(2,-1),'Helvetica-Bold'),
            ('FONTNAME',(4,0),(4,-1),'Helvetica-Bold'),
            ('FONTSIZE',(0,0),(-1,-1),9),
            ('ROWBACKGROUNDS',(0,0),(-1,-1),[colors.white, BG]),
            ('GRID',(0,0),(-1,-1),0.4,colors.HexColor('#ddd9d1')),
            ('PADDING',(0,0),(-1,-1),5),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ]))
        story.append(it)
        story.append(Spacer(1,10))

        story.append(Paragraph('Summary', h2))
        story.append(Paragraph(result.get('summary','—'), body))

        alerts = result.get('critical_alerts', [])
        if alerts:
            story.append(Spacer(1,8))
            story.append(Paragraph('⚠ Critical Alerts',
                S('ah', fontSize=13, textColor=RED, fontName='Helvetica-Bold', spaceAfter=6)))
            for a in alerts:
                story.append(Paragraph(f'• {a}',
                    S('al', fontSize=10, textColor=RED, leading=16, leftIndent=12)))

        params = result.get('parameters', [])
        if params:
            story.append(Spacer(1,10))
            story.append(Paragraph('Laboratory Parameters', h2))
            tdata = [['Parameter','Value','Normal Range','Status','Interpretation']]
            for p in params:
                st = p.get('status','Normal')
                sc = RED if ('High' in st or 'Critical' in st) else (AMBER if 'Low' in st else GREEN)
                tdata.append([
                    Paragraph(p.get('name',''), tc),
                    Paragraph(f'<b>{p.get("value","")}</b>', tc),
                    Paragraph(p.get('normal_range',''), tc8),
                    Paragraph(f'<font color="{sc.hexval()}"><b>{st}</b></font>', tc),
                    Paragraph(p.get('interpretation',''), tc8),
                ])
            pt = Table(tdata, colWidths=[3.5*cm,2.5*cm,3.5*cm,2.5*cm,5.5*cm])
            pt.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),GREEN),
                ('TEXTCOLOR',(0,0),(-1,0),colors.white),
                ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
                ('FONTSIZE',(0,0),(-1,0),9),
                ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,BG]),
                ('GRID',(0,0),(-1,-1),0.3,colors.HexColor('#ddd9d1')),
                ('PADDING',(0,0),(-1,-1),5),
                ('VALIGN',(0,0),(-1,-1),'TOP'),
            ]))
            story.append(pt)

        conditions = result.get('conditions_identified', [])
        if conditions:
            story.append(Spacer(1,10))
            story.append(Paragraph('Conditions Identified', h2))
            for c in conditions:
                conf = c.get('confidence','')
                cc = RED if conf=='High' else (AMBER if conf=='Moderate' else MUTED)
                story.append(Paragraph(
                    f'<b>{c.get("condition","")}</b> — '
                    f'<font color="{cc.hexval()}">{conf} confidence</font>', body))
                story.append(Paragraph(f'Evidence: {c.get("evidence","")}', sm))

        recs = result.get('recommendations', [])
        if recs:
            story.append(Spacer(1,10))
            story.append(Paragraph('Recommendations', h2))
            pc_map = {'Urgent':RED,'High':RED,'Medium':AMBER,'Low':GREEN}
            for r in recs:
                pr = r.get('priority','Low')
                pc = pc_map.get(pr, MUTED)
                story.append(Paragraph(
                    f'<font color="{pc.hexval()}"><b>[{pr}]</b></font> {r.get("action","")}',
                    S('rc', fontSize=10, leading=16, leftIndent=8)))

        lifestyle = result.get('lifestyle_advice', [])
        if lifestyle:
            story.append(Spacer(1,10))
            story.append(Paragraph('Lifestyle Advice', h2))
            for l in lifestyle:
                story.append(Paragraph(f'✓ {l}',
                    S('lf', fontSize=10, leading=16, leftIndent=8)))

        if result.get('followup'):
            story.append(Spacer(1,10))
            story.append(Paragraph('Follow-up', h2))
            story.append(Paragraph(result['followup'], body))

        story.append(Spacer(1,8))
        story.append(HRFlowable(width='100%', color=colors.HexColor('#ddd9d1'), thickness=0.5))
        story.append(Spacer(1,6))
        story.append(Paragraph(f'⚕ {result.get("disclaimer","")}', disc))

        doc.build(story)
        return True

    except Exception as e:
        print(f'[PDF] Error: {e} — falling back to simple PDF')
        _simple_pdf(result, name, age, gender, output_path)
        return True


def _simple_pdf(result, name, age, gender, output_path):
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
        c = canvas.Canvas(output_path, pagesize=A4)
        w, h = A4
        y = h - 60
        c.setFont('Helvetica-Bold', 16)
        c.drawString(50, y, 'MediScan AI Report'); y -= 30
        c.setFont('Helvetica', 11)
        for line in [f'Patient: {name}', f'Age: {age}', f'Gender: {gender}',
                     f'Risk Level: {result.get("risk_level","?")}',
                     f'Risk Score: {result.get("risk_score","?")}', '',
                     result.get('summary', '')[:120]]:
            c.drawString(50, y, str(line)); y -= 18
            if y < 60: c.showPage(); y = h - 60
        c.save()
    except Exception as e:
        print(f'[PDF fallback] Error: {e}')


# ── Image (PNG / JPG) ────────────────────────────────────────────────────────

def generate_image_report(result, name, age, gender, output_path, fmt='PNG'):
    try:
        from PIL import Image, ImageDraw, ImageFont

        W, H   = 900, 1500
        BG     = (244, 241, 236)
        WHITE  = (255, 255, 255)
        GREEN  = (45, 106, 79)
        AMBER  = (183, 112, 13)
        RED    = (193, 57, 43)
        BLUE   = (24, 95, 165)
        TEXT   = (28, 26, 23)
        MUTED  = (122, 117, 110)
        LGREY  = (237, 233, 226)

        img  = Image.new('RGB', (W, H), BG)
        draw = ImageDraw.Draw(img)
        y    = [0]   # mutable so inner functions can update it

        def fnt(size, bold=False):
            try:
                import platform
                if platform.system() == 'Windows':
                    path = r'C:\Windows\Fonts\arialbd.ttf' if bold else r'C:\Windows\Fonts\arial.ttf'
                else:
                    path = ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold
                            else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
                return ImageFont.truetype(path, size)
            except Exception:
                return ImageFont.load_default()

        def txt_w(text, f):
            try:
                return draw.textlength(text, font=f)
            except Exception:
                return len(text) * (f.size if hasattr(f,'size') else 7)

        def wrap_text(text, f, max_w):
            words = str(text).split()
            lines, line = [], ''
            for w in words:
                test = (line + ' ' + w).strip()
                if txt_w(test, f) > max_w:
                    if line: lines.append(line)
                    line = w
                else:
                    line = test
            if line: lines.append(line)
            return lines or ['']

        def draw_text_wrapped(text, f, x, color, max_w, line_h=18):
            for line in wrap_text(text, f, max_w):
                if y[0] < H - 20:
                    draw.text((x, y[0]), line, font=f, fill=color)
                y[0] += line_h

        def section_bar(title, bg=GREEN):
            draw.rectangle([0, y[0], W, y[0]+32], fill=bg)
            draw.text((16, y[0]+7), title, font=fnt(12, True), fill=WHITE)
            y[0] += 38

        def hline(color=LGREY):
            draw.line([16, y[0], W-16, y[0]], fill=color, width=1)
            y[0] += 6

        # ── Header ──────────────────────────────────────────────────────────
        draw.rectangle([0, 0, W, 82], fill=GREEN)
        draw.text((W//2, 16), 'MediScan AI', font=fnt(26, True), fill=WHITE, anchor='mt')
        draw.text((W//2, 52), 'AI-Powered Medical Report Analysis', font=fnt(13), fill=(180,220,200), anchor='mt')
        y[0] = 90

        # ── Patient info ─────────────────────────────────────────────────────
        draw.rectangle([12, y[0], W-12, y[0]+100], fill=WHITE, outline=LGREY, width=1)
        y[0] += 10
        draw.text((24, y[0]), f'Patient: {name}', font=fnt(12, True), fill=TEXT); y[0] += 22
        draw.text((24, y[0]), f'Age: {age}   |   Gender: {gender}', font=fnt(11), fill=MUTED); y[0] += 22

        risk  = result.get('risk_level', 'Unknown')
        score = result.get('risk_score', 0)
        rc    = RED if risk == 'Critical' else (AMBER if 'Attention' in risk else GREEN)
        draw.text((24, y[0]), f'Risk Level: {risk}   |   Score: {score}/100',
                  font=fnt(12, True), fill=rc); y[0] += 22
        draw.text((24, y[0]),
                  f'Date: {datetime.now().strftime("%d %b %Y")}   |   {result.get("ai_provider","AI")}',
                  font=fnt(10), fill=MUTED)
        y[0] = 200

        # ── Summary ──────────────────────────────────────────────────────────
        section_bar('Summary')
        draw_text_wrapped(result.get('summary',''), fnt(10), 16, TEXT, W-32)
        y[0] += 8

        # ── Critical alerts ───────────────────────────────────────────────────
        alerts = result.get('critical_alerts', [])
        if alerts:
            section_bar('⚠  Critical Alerts', RED)
            for a in alerts[:6]:
                draw_text_wrapped(f'•  {a}', fnt(10), 20, RED, W-40)
            y[0] += 6

        # ── Parameters ───────────────────────────────────────────────────────
        params = result.get('parameters', [])
        if params:
            section_bar('Laboratory Parameters')
            # header row
            hrow_y = y[0]
            draw.rectangle([12, hrow_y, W-12, hrow_y+22], fill=LGREY)
            for x_pos, lbl in [(14,'Parameter'),(220,'Value'),(360,'Normal Range'),(560,'Status')]:
                draw.text((x_pos+2, hrow_y+4), lbl, font=fnt(9,True), fill=MUTED)
            y[0] += 22

            for i, p in enumerate(params[:18]):
                row_bg = WHITE if i % 2 == 0 else BG
                draw.rectangle([12, y[0], W-12, y[0]+22], fill=row_bg)
                st = p.get('status','Normal')
                fc = RED if ('High' in st or 'Critical' in st) else (AMBER if 'Low' in st else GREEN)
                draw.text((16,   y[0]+4), str(p.get('name',''))[:28],         font=fnt(9),      fill=TEXT)
                draw.text((220,  y[0]+4), str(p.get('value',''))[:18],        font=fnt(9,True), fill=TEXT)
                draw.text((360,  y[0]+4), str(p.get('normal_range',''))[:26], font=fnt(9),      fill=MUTED)
                draw.text((560,  y[0]+4), str(st)[:22],                       font=fnt(9,True), fill=fc)
                y[0] += 22
                if y[0] > H - 140: break
            y[0] += 8

        # ── Conditions ───────────────────────────────────────────────────────
        conditions = result.get('conditions_identified', [])
        if conditions and y[0] < H - 180:
            section_bar('Conditions Identified')
            for c in conditions[:5]:
                conf = c.get('confidence','')
                cc   = RED if conf=='High' else (AMBER if conf=='Moderate' else GREEN)
                draw.text((16, y[0]), f'{c.get("condition","")}', font=fnt(10,True), fill=TEXT)
                y[0] += 18
                draw.text((16, y[0]), f'Confidence: {conf}   Evidence: {c.get("evidence","")}',
                          font=fnt(9), fill=MUTED)
                y[0] += 20
            y[0] += 4

        # ── Recommendations ───────────────────────────────────────────────────
        recs = result.get('recommendations', [])
        if recs and y[0] < H - 180:
            section_bar('Recommendations')
            pc_map = {'Urgent': RED, 'High': RED, 'Medium': AMBER, 'Low': GREEN}
            for r in recs[:6]:
                pr = r.get('priority','Low')
                pc = pc_map.get(pr, GREEN)
                pw = int(txt_w(f'[{pr}] ', fnt(10,True)))
                draw.text((16, y[0]), f'[{pr}]', font=fnt(10,True), fill=pc)
                draw_text_wrapped(r.get('action',''), fnt(10), 16+pw, TEXT, W-32-pw)
            y[0] += 4

        # ── Disclaimer ────────────────────────────────────────────────────────
        if y[0] < H - 60:
            draw.rectangle([12, y[0], W-12, y[0]+50], fill=(232,240,251), outline=(197,216,245), width=1)
            disc = result.get('disclaimer','This is AI-generated. Consult a healthcare provider.')
            draw.text((20, y[0]+8),  '⚕  ' + disc[:100], font=fnt(9), fill=BLUE)
            if len(disc) > 100:
                draw.text((20, y[0]+24), disc[100:210], font=fnt(9), fill=BLUE)

        # ── Save ──────────────────────────────────────────────────────────────
        if fmt == 'JPEG':
            img.convert('RGB').save(output_path, 'JPEG', quality=92)
        else:
            img.save(output_path, 'PNG')
        return True

    except Exception as e:
        print(f'[Image report] Error: {e}')
        return False
