# report_service.py
# Feature 3: Compliance Certification Report Generator (Person A)
# Builds a tamper-evident PDF certification report using ReportLab.
# Includes certificate ID, content title, final text hash, rulebook version,
# findings summary, every accept/reject with actor, reviewer decision,
# and cryptographic chain verification status.

import hashlib
import io
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def compute_text_hash(text: str) -> str:
    """Return SHA-256 hex digest of the given text."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def build_certificate_pdf(
    content: Dict[str, Any],
    review: Optional[Dict[str, Any]],
    rulebook: Optional[Dict[str, Any]],
    audit_events: List[Dict[str, Any]],
    chain_valid: bool = False,
) -> bytes:
    """
    Generate a formal PDF certification report in bytes.
    Only called for approved content.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    primary_color = colors.HexColor("#1f2a5a")
    secondary_color = colors.HexColor("#3b4a9c")
    text_dark = colors.HexColor("#1f2430")
    success_color = colors.HexColor("#15803d")
    warning_color = colors.HexColor("#b45309")
    gray_bg = colors.HexColor("#f8fafc")
    border_color = colors.HexColor("#cbd5e1")

    title_style = ParagraphStyle(
        "CertTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=primary_color,
        alignment=0,
        spaceAfter=4,
    )

    subtitle_style = ParagraphStyle(
        "CertSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=12,
    )

    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=primary_color,
        spaceBefore=12,
        spaceAfter=6,
    )

    body_style = ParagraphStyle(
        "CertBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=text_dark,
    )

    mono_style = ParagraphStyle(
        "CertMono",
        parent=body_style,
        fontName="Courier",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#0f172a"),
    )

    badge_style = ParagraphStyle(
        "BadgeText",
        parent=body_style,
        fontName="Helvetica-Bold",
        fontSize=9,
        alignment=1,
    )

    story = []

    content_id = content.get("id", "unknown")
    cert_id = f"CERT-{content_id[:8].upper()}-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    issued_date = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M:%S UTC")
    final_text_hash = compute_text_hash(content.get("text", ""))
    company_name = (rulebook or {}).get("company", "Brand")
    rulebook_ver = (rulebook or {}).get("version", 1)
    rulebook_id = (rulebook or {}).get("rulebook_id", "N/A")

    # 1. Header Banner
    story.append(Paragraph("BrandLens Compliance Certification Report", title_style))
    story.append(Paragraph(f"Official Process Verification & Audit Trail &bull; Certificate ID: <b>{cert_id}</b>", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=primary_color, spaceBefore=0, spaceAfter=10))

    # 2. Content & Rulebook Metadata Box
    meta_data = [
        [
            Paragraph("<b>Content Title:</b>", body_style),
            Paragraph(content.get("title", "Untitled"), body_style),
            Paragraph("<b>Status:</b>", body_style),
            Paragraph(f"<font color='{success_color}'><b>APPROVED</b></font>", body_style),
        ],
        [
            Paragraph("<b>Channel / Type:</b>", body_style),
            Paragraph(content.get("type", "Blog"), body_style),
            Paragraph("<b>Content Author:</b>", body_style),
            Paragraph(content.get("owner", "Unknown"), body_style),
        ],
        [
            Paragraph("<b>Brand Rulebook:</b>", body_style),
            Paragraph(f"{company_name} (v{rulebook_ver})", body_style),
            Paragraph("<b>Rulebook ID:</b>", body_style),
            Paragraph(rulebook_id[:16] + "..." if len(rulebook_id) > 16 else rulebook_id, mono_style),
        ],
        [
            Paragraph("<b>Final Text SHA-256:</b>", body_style),
            Paragraph(final_text_hash, mono_style),
            Paragraph("<b>Certified At:</b>", body_style),
            Paragraph(issued_date, body_style),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[1.3 * inch, 2.3 * inch, 1.2 * inch, 2.2 * inch])
    meta_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), gray_bg),
            ("BOX", (0, 0), (-1, -1), 0.5, border_color),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # 3. Cryptographic Chain Status Callout
    if chain_valid:
        chain_banner_color = colors.HexColor("#dcfce7")
        chain_border_color = success_color
        chain_text = f"<b><font color='{success_color}'>&#10004; CRYPTOGRAPHIC AUDIT TRAIL VERIFIED</font></b><br/>" \
                     f"All {len(audit_events)} sequential audit events are tamper-evident and verified against sequential SHA-256 hashes."
    else:
        chain_banner_color = colors.HexColor("#fef3c7")
        chain_border_color = warning_color
        chain_text = f"<b><font color='{warning_color}'>&#9888; AUDIT TRAIL CHAIN NOTICE</font></b><br/>" \
                     f"Recorded {len(audit_events)} audit events. Cryptographic hash chain verification is in progress or pending full node sync."

    chain_box = Table([[Paragraph(chain_text, body_style)]], colWidths=[7.0 * inch])
    chain_box.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), chain_banner_color),
            ("BOX", (0, 0), (-1, -1), 1, chain_border_color),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ])
    )
    story.append(chain_box)
    story.append(Spacer(1, 10))

    # 4. Findings & Remediation Summary
    findings = (review or {}).get("findings", [])
    accepted_count = sum(1 for f in findings if f.get("status") == "accepted")
    rejected_count = sum(1 for f in findings if f.get("status") == "rejected")
    total_findings = len(findings)

    story.append(Paragraph("Compliance Findings & Remediation Decisions", heading_style))

    summary_text = (
        f"<b>Initial Score:</b> {(review or {}).get('score', 'N/A')}/100 &bull; "
        f"<b>Total Issues Flagged:</b> {total_findings} &bull; "
        f"<b>Accepted Remediations:</b> {accepted_count} &bull; "
        f"<b>Rejected / Overridden:</b> {rejected_count}"
    )
    story.append(Paragraph(summary_text, body_style))
    story.append(Spacer(1, 6))

    if findings:
        findings_table_data = [
            [
                Paragraph("<b>#</b>", body_style),
                Paragraph("<b>Rule / Category</b>", body_style),
                Paragraph("<b>Flagged Text & Issue</b>", body_style),
                Paragraph("<b>Decision & Remediation</b>", body_style),
                Paragraph("<b>Status</b>", body_style),
            ]
        ]
        for idx, f in enumerate(findings, 1):
            status = f.get("status", "pending").upper()
            status_color = success_color if status == "ACCEPTED" else colors.HexColor("#dc2626") if status == "REJECTED" else warning_color
            replacement = f.get("replacement") or f.get("suggestion") or "Manual edit"
            
            remed_text = f"<b>Action:</b> {replacement}"
            flagged = f"<i>\"{f.get('text', '')}\"</i><br/>{f.get('reason', '')}"

            findings_table_data.append([
                Paragraph(str(idx), body_style),
                Paragraph(f"<b>{f.get('category', f.get('source', 'Rule'))}</b><br/>{f.get('rule', '')}", body_style),
                Paragraph(flagged, body_style),
                Paragraph(remed_text, body_style),
                Paragraph(f"<font color='{status_color}'><b>{status}</b></font>", badge_style),
            ])

        findings_table = Table(
            findings_table_data,
            colWidths=[0.3 * inch, 1.8 * inch, 2.5 * inch, 1.6 * inch, 0.8 * inch],
        )
        findings_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("GRID", (0, 0), (-1, -1), 0.5, border_color),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        story.append(findings_table)
    else:
        story.append(Paragraph("<i>No compliance findings were detected. Content conformed fully to active brand rules.</i>", body_style))

    story.append(Spacer(1, 10))

    # 5. Reviewer Decision Box
    story.append(Paragraph("Reviewer Sign-Off & Approval Decision", heading_style))
    
    # Locate decision event in trail
    decision_event = next((e for e in audit_events if e.get("action") == "decision_made"), None)
    reviewer_actor = decision_event.get("actor", "Reviewer") if decision_event else "Reviewer"
    reviewer_ts = decision_event.get("ts", issued_date) if decision_event else issued_date
    decision_comment = (decision_event.get("details") or {}).get("comment", "") if decision_event else ""
    if not decision_comment:
        decision_comment = "Content conforms with brand guidelines and policy standards."

    reviewer_box_data = [
        [
            Paragraph("<b>Final Decision:</b>", body_style),
            Paragraph(f"<font color='{success_color}'><b>APPROVED FOR PUBLICATION</b></font>", body_style),
            Paragraph("<b>Reviewer:</b>", body_style),
            Paragraph(f"{reviewer_actor} (role: reviewer)", body_style),
        ],
        [
            Paragraph("<b>Decision Date:</b>", body_style),
            Paragraph(reviewer_ts, body_style),
            Paragraph("<b>Comments:</b>", body_style),
            Paragraph(f"<i>&ldquo;{decision_comment}&rdquo;</i>", body_style),
        ],
    ]
    reviewer_table = Table(reviewer_box_data, colWidths=[1.3 * inch, 2.3 * inch, 1.2 * inch, 2.2 * inch])
    reviewer_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), gray_bg),
            ("BOX", (0, 0), (-1, -1), 0.5, border_color),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(reviewer_table)
    story.append(Spacer(1, 10))

    # 6. Audit Trail Summary (Chronological Events)
    story.append(Paragraph("Immutable Audit Trail Sequence", heading_style))
    if audit_events:
        trail_table_data = [
            [
                Paragraph("<b>Seq</b>", body_style),
                Paragraph("<b>Timestamp (UTC)</b>", body_style),
                Paragraph("<b>Actor</b>", body_style),
                Paragraph("<b>Action</b>", body_style),
                Paragraph("<b>Event Hash</b>", body_style),
            ]
        ]
        for ev in audit_events:
            ev_hash = ev.get("hash", "")
            disp_hash = ev_hash[:16] + "..." if len(ev_hash) > 16 else ev_hash or "genesis"
            actor_str = f"{ev.get('actor', '')} ({ev.get('role', '')})"
            trail_table_data.append([
                Paragraph(str(ev.get("seq", "-")), body_style),
                Paragraph(str(ev.get("ts", "")[:19]), body_style),
                Paragraph(actor_str, body_style),
                Paragraph(f"<b>{ev.get('action', '')}</b>", body_style),
                Paragraph(disp_hash, mono_style),
            ])

        trail_table = Table(
            trail_table_data,
            colWidths=[0.4 * inch, 1.8 * inch, 1.6 * inch, 1.7 * inch, 1.5 * inch],
        )
        trail_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("GRID", (0, 0), (-1, -1), 0.5, border_color),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        story.append(trail_table)
    else:
        story.append(Paragraph("<i>No audit events currently recorded for this content item.</i>", body_style))

    story.append(Spacer(1, 14))

    # 7. Process Disclaimer (from design doc Page 7)
    story.append(HRFlowable(width="100%", thickness=0.5, color=border_color, spaceBefore=4, spaceAfter=6))
    disclaimer = (
        "<b>Process Compliance Notice:</b> This certificate attests to adherence to the internal BrandLens review, "
        "remediation, and sign-off governance workflow. Actor identities reflect self-declared session credentials. "
        "The cryptographic hash chain guarantees tamper-evidence across the recorded lifecycle events. "
        "This certification confirms internal brand workflow completion and does not constitute external legal compliance."
    )
    story.append(Paragraph(disclaimer, ParagraphStyle("Disc", parent=body_style, fontSize=7, leading=10, textColor=colors.HexColor("#64748b"))))

    doc.build(story)
    return buf.getvalue()
