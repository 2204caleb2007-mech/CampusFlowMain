# ============================================================
# campus/pdf_exporter.py — Chat to PDF Generation
# ============================================================
# Converts a CampusFlow SQLite chat session into a formatted
# PDF document using ReportLab.
# ============================================================

import io
import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from campus import db

def generate_chat_pdf(session_id: str, username: str, user_role: str) -> bytes:
    """
    Generate a PDF of the specified chat session.
    Returns the PDF file as bytes, or an empty bytes string on failure.
    """
    session = db.get_session(session_id)
    if not session:
        return b""
        
    messages = db.get_messages(session_id)
    if not messages:
        return b""

    title = session.get("title", "CampusFlow Conversation")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
        title=f"Chat Export: {title}"
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    header_style = ParagraphStyle(
        'HeaderStyle', parent=styles['Heading1'],
        fontSize=18, textColor=colors.darkblue, spaceAfter=6
    )
    meta_style = ParagraphStyle(
        'MetaStyle', parent=styles['Normal'],
        fontSize=10, textColor=colors.gray, spaceAfter=4
    )
    user_label = ParagraphStyle(
        'UserLabel', parent=styles['Normal'],
        fontSize=11, fontName='Helvetica-Bold', textColor=colors.darkgreen, spaceBefore=10
    )
    ai_label = ParagraphStyle(
        'AILabel', parent=styles['Normal'],
        fontSize=11, fontName='Helvetica-Bold', textColor=colors.darkblue, spaceBefore=10
    )
    msg_style = ParagraphStyle(
        'MessageContent', parent=styles['Normal'],
        fontSize=11, spaceAfter=8, leading=14
    )

    story = []
    
    # ── Header ──
    story.append(Paragraph(f"CampusFlow Chat Export", header_style))
    story.append(Paragraph(f"<b>Session ID:</b> {session_id}", meta_style))
    story.append(Paragraph(f"<b>Session Name:</b> {title}", meta_style))
    story.append(Paragraph(f"<b>Requested By:</b> {username} ({user_role.title()})", meta_style))
    story.append(Paragraph(f"<b>Exported Date:</b> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", meta_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey, spaceBefore=8, spaceAfter=16))

    # ── Messages ──
    for msg in messages:
        role = msg.get("role", "unknown")
        # Replace newlines with bold HTML tags and handle markdown safely
        content = str(msg.get("content", "")).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        content = content.replace('\n', '<br/>')
        
        ts = str(msg.get("created_at", ""))[:19].replace("T", " ")
        
        if role == "user":
            story.append(Paragraph(f"User [{ts}]:", user_label))
        elif role == "assistant":
            story.append(Paragraph(f"CampusBot [{ts}]:", ai_label))
        else:
            story.append(Paragraph(f"{role.title()} [{ts}]:", user_label))
            
        story.append(Paragraph(content, msg_style))
        story.append(Spacer(1, 4))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.whitesmoke, spaceBefore=2, spaceAfter=2))

    # Build PDF
    doc.build(story)
    
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
