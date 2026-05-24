"""
Unit-тесты: ReconciliationEngine
"""
from datetime import date

from app.services.reconciliation.engine import (
    compute_reconciliation,
    normalize_name,
)


class TestNormalizeName:
    def test_strips_prefix_ooo(self):
        assert normalize_name('ООО "Альфа"') == "альфа"

    def test_strips_ip_prefix(self):
        assert normalize_name("ИП Бетов") == "бетов"

    def test_empty_safe(self):
        assert normalize_name("  ") == ""


class TestComputeReconciliation:
    AS_OF = date(2026, 5, 24)

    def test_empty_if_only_receivables(self):
        rcv = [{"counterparty": "ООО Альфа", "amount": 100000, "due_date": self.AS_OF}]
        assert compute_reconciliation(rcv, [], self.AS_OF) == []

    def test_empty_if_only_bank(self):
        bank = [{"counterparty": "ООО Альфа", "amount": 100000, "txn_date": self.AS_OF}]
        assert compute_reconciliation([], bank, self.AS_OF) == []

    def test_erp_only_overdue_no_bank(self):
        rcv = [
            {
                "counterparty": "ООО Альфа",
                "amount": 150000,
                "due_date": date(2026, 5, 1),
                "status": "overdue",
            }
        ]
        bank = [{"counterparty": "ЗАО Другой", "amount": 50000, "txn_date": self.AS_OF}]
        issues = compute_reconciliation(rcv, bank, self.AS_OF)
        kinds = {i.kind for i in issues}
        assert "erp_only" in kinds
        erp = next(i for i in issues if i.kind == "erp_only")
        assert erp.counterparty == "ООО Альфа"
        assert erp.amount == 150000

    def test_bank_only_no_receivable(self):
        rcv = [
            {
                "counterparty": "ООО Альфа",
                "amount": 100000,
                "due_date": date(2026, 6, 1),
                "status": "open",
            }
        ]
        bank = [{"counterparty": "ИП Новый клиент", "amount": 80000, "txn_date": self.AS_OF}]
        issues = compute_reconciliation(rcv, bank, self.AS_OF)
        bank_only = [i for i in issues if i.kind == "bank_only"]
        assert len(bank_only) == 1
        assert bank_only[0].amount == 80000

    def test_amount_mismatch(self):
        rcv = [
            {
                "counterparty": "ООО Альфа",
                "amount": 100000,
                "due_date": date(2026, 5, 1),
                "status": "open",
            }
        ]
        bank = [{"counterparty": 'ООО "Альфа"', "amount": 50000, "txn_date": self.AS_OF}]
        issues = compute_reconciliation(rcv, bank, self.AS_OF)
        mismatch = [i for i in issues if i.kind == "amount_mismatch"]
        assert len(mismatch) == 1

    def test_no_issue_when_amounts_match(self):
        rcv = [
            {
                "counterparty": "ООО Альфа",
                "amount": 100000,
                "due_date": date(2026, 5, 1),
                "status": "open",
            }
        ]
        bank = [{"counterparty": "ООО Альфа", "amount": 100000, "txn_date": self.AS_OF}]
        issues = compute_reconciliation(rcv, bank, self.AS_OF)
        assert issues == []

    def test_future_receivable_not_erp_only(self):
        rcv = [
            {
                "counterparty": "ООО Будущее",
                "amount": 200000,
                "due_date": date(2026, 8, 1),
                "status": "open",
            }
        ]
        bank = [{"counterparty": "ИП Другой", "amount": 10000, "txn_date": self.AS_OF}]
        issues = compute_reconciliation(rcv, bank, self.AS_OF)
        erp = [i for i in issues if i.kind == "erp_only" and i.counterparty == "ООО Будущее"]
        assert erp == []

    def test_max_ten_issues(self):
        rcv = [
            {
                "counterparty": f"ООО К{i}",
                "amount": 1000 * (i + 1),
                "due_date": date(2026, 5, 1),
                "status": "open",
            }
            for i in range(15)
        ]
        bank = [{"counterparty": "ИП Единственный", "amount": 500, "txn_date": self.AS_OF}]
        issues = compute_reconciliation(rcv, bank, self.AS_OF)
        assert len(issues) <= 10
