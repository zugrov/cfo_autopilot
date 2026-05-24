"""
PDF-генератор еженедельного управленческого отчёта.
"""
from __future__ import annotations

import io
import os
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services.report.actions import build_recommended_actions

_FONT_NAME = "ReportFont"
_FONT_REGISTERED = False


def _register_font() -> str:
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return _FONT_NAME

    candidates = [
        os.path.join(os.path.dirname(__file__), "assets", "DejaVuSans.ttf"),
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.isfile(path):
            pdfmetrics.registerFont(TTFont(_FONT_NAME, path))
            _FONT_REGISTERED = True
            return _FONT_NAME

    _FONT_REGISTERED = True
    return "Helvetica"


def _money(amount: float | None) -> str:
    if amount is None:
        return "—"
    return f"₽ {amount:,.0f}".replace(",", " ")


def _parse_date(value: str | None) -> str:
    if not value:
        return "—"
    try:
        return date.fromisoformat(value[:10]).strftime("%d.%m.%Y")
    except ValueError:
        return value


def render_weekly_pdf(context: dict, company_name: str) -> bytes:
    """Рендерит PDF-отчёт и возвращает bytes."""
    font = _register_font()
    buffer = io.BytesIO()
    as_of = _parse_date(context.get("as_of"))

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        fontName=font,
        fontSize=16,
        spaceAfter=6,
    )
    heading_style = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontName=font,
        fontSize=12,
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName=font,
        fontSize=10,
        leading=14,
    )

    story: list = []
    story.append(Paragraph("Управленческий дайджест", title_style))
    story.append(Paragraph(f"{company_name} — за неделю по {as_of}", body_style))
    story.append(Spacer(1, 0.4 * cm))

    # Резюме
    story.append(Paragraph("Резюме", heading_style))
    if context.get("has_data"):
        story.append(
            Paragraph(f"Остаток: <b>{_money(context.get('balance'))}</b>", body_style)
        )
        explain = context.get("explain") or {}
        if explain.get("headline"):
            story.append(Paragraph(explain["headline"], body_style))
        for reason in (explain.get("reasons") or [])[:3]:
            line = f"• {reason.get('label', '')} — {_money(reason.get('amount'))}"
            story.append(Paragraph(line, body_style))
    else:
        story.append(Paragraph("Данные не загружены.", body_style))

    # Риски
    story.append(Paragraph("Риски", heading_style))
    forecast = context.get("forecast") or {}
    signal = forecast.get("deficit_signal")
    if signal:
        stress = " (стресс-сценарий −15%)" if signal.get("is_stress") else ""
        story.append(
            Paragraph(
                f"Кассовый разрыв возможен {signal.get('days_until')} дн. "
                f"({ _parse_date(signal.get('date')) }){stress}",
                body_style,
            )
        )
    else:
        story.append(Paragraph("Сигнал кассового разрыва не выявлен.", body_style))

    stress_days = forecast.get("days_stress") or []
    if stress_days:
        story.append(
            Paragraph(
                f"Стресс-дней в прогнозе: {len(stress_days)}",
                body_style,
            )
        )

    # Обязательства
    story.append(Paragraph("Ближайшие обязательства", heading_style))
    obligations = context.get("obligations") or []
    if obligations:
        ob_rows = [["Дата", "Сумма", "Описание"]]
        for ob in obligations[:5]:
            ob_rows.append([
                _parse_date(ob.get("due_date")),
                _money(ob.get("amount")),
                ob.get("description") or "—",
            ])
        table = Table(ob_rows, colWidths=[3 * cm, 3.5 * cm, 9 * cm])
        table.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), font),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ])
        )
        story.append(table)
    else:
        story.append(Paragraph("Нет предстоящих обязательств.", body_style))

    # Дебиторка
    receivables = context.get("receivables")
    if receivables:
        story.append(Paragraph("Дебиторская задолженность", heading_style))
        story.append(
            Paragraph(
                f"Открыто: {_money(receivables.get('total_open'))}",
                body_style,
            )
        )
        for bucket in receivables.get("buckets") or []:
            story.append(
                Paragraph(
                    f"• {bucket.get('bucket')}: {_money(bucket.get('amount'))} "
                    f"({bucket.get('count')} поз.)",
                    body_style,
                )
            )

    # Сверка
    reconciliation = context.get("reconciliation")
    if reconciliation:
        story.append(Paragraph("Сверка банк / 1С", heading_style))
        if reconciliation.get("has_issues"):
            for issue in (reconciliation.get("issues") or [])[:5]:
                story.append(
                    Paragraph(
                        f"• {issue.get('counterparty')}: {issue.get('detail')}",
                        body_style,
                    )
                )
        else:
            story.append(Paragraph("Расхождений не обнаружено.", body_style))

    # Рекомендации
    story.append(Paragraph("Рекомендуемые действия", heading_style))
    for action in build_recommended_actions(context):
        story.append(Paragraph(f"• {action}", body_style))

    # Футер
    story.append(Spacer(1, 0.6 * cm))
    last_import = context.get("last_import_at")
    footer = "Отчёт сформирован автоматически. Данные могут быть неполными."
    if last_import:
        footer += f" Последний импорт: {last_import[:10]}."
    story.append(Paragraph(footer, body_style))

    doc.build(story)
    return buffer.getvalue()
