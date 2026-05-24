"""
Rule-based рекомендуемые действия для управленческого отчёта.
"""
from __future__ import annotations


def build_recommended_actions(context: dict) -> list[str]:
    """Формирует список рекомендаций без LLM."""
    actions: list[str] = []

    stale = context.get("stale") or {}
    if stale.get("is_stale"):
        hours = stale.get("hours")
        if hours:
            actions.append(f"Обновите банковскую выписку — данные не обновлялись {hours} ч.")
        else:
            actions.append("Обновите банковскую выписку — данные устарели.")

    forecast = context.get("forecast") or {}
    signal = forecast.get("deficit_signal")
    if signal and signal.get("severity") in ("critical", "warning"):
        gap_date = signal.get("date", "")
        actions.append(
            f"Проверьте обязательства и поступления на {gap_date} — "
            f"риск кассового разрыва через {signal.get('days_until')} дн."
        )

    reconciliation = context.get("reconciliation")
    if reconciliation and reconciliation.get("has_issues"):
        count = len(reconciliation.get("issues") or [])
        actions.append(
            f"Сверьте поступления с данными 1С — обнаружено {count} расхождений."
        )

    receivables = context.get("receivables")
    if receivables:
        for bucket in receivables.get("buckets") or []:
            if bucket.get("bucket") == "overdue" and bucket.get("amount", 0) > 0:
                actions.append("Проконтролируйте просроченную дебиторскую задолженность.")
                break

    if not context.get("has_data"):
        actions.append("Загрузите банковскую выписку для формирования прогноза.")

    if not actions:
        actions.append("Критичных рисков не выявлено — продолжайте мониторинг в личном кабинете.")

    return actions
