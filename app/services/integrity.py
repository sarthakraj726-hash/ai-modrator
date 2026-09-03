"""Database and domain integrity verification service."""

from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.models.economy import EconomyAccount, EconomyLedgerEntry
from app.db.models.store import StoreItem, ViewerInventory
from app.db.models.stream_session import StreamSession, StreamStatus

logger = get_logger("app.services.integrity")


class IntegrityViolation(BaseModel):
    category: str
    severity: str  # WARNING, ERROR, CRITICAL
    entity_id: str | None = None
    details: str
    context: dict[str, Any] = Field(default_factory=dict)


class IntegrityAuditReport(BaseModel):
    timestamp: datetime
    is_valid: bool
    violations: list[IntegrityViolation] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)


class IntegrityCheckService:
    """
    Automated background audit service ensuring:
    1. Double-entry ledger equality: sum(Debits) == sum(Credits) == 0.
    2. Non-negative account balances.
    3. Store inventory consistency.
    4. Stale/hung stream session detection.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def run_full_audit(self) -> IntegrityAuditReport:
        """Run all verification checks and return audit report."""
        violations: list[IntegrityViolation] = []
        stats: dict[str, Any] = {}

        # 1. Audit Double-Entry Ledger Equality
        ledger_violations, ledger_stats = await self.audit_economy_ledger()
        violations.extend(ledger_violations)
        stats["ledger"] = ledger_stats

        # 2. Audit Non-Negative Balances
        balance_violations, balance_stats = await self.audit_account_balances()
        violations.extend(balance_violations)
        stats["balances"] = balance_stats

        # 3. Audit Store Inventory Consistency
        store_violations, store_stats = await self.audit_store_inventory()
        violations.extend(store_violations)
        stats["store"] = store_stats

        # 4. Audit Stale Stream Sessions
        session_violations, session_stats = await self.audit_stale_stream_sessions()
        violations.extend(session_violations)
        stats["sessions"] = session_stats

        is_valid = len(violations) == 0
        if not is_valid:
            logger.error(
                f"Integrity check failed with {len(violations)} violations: "
                f"{[v.details for v in violations]}"
            )
        else:
            logger.info("Integrity check completed successfully. 0 violations found.")

        return IntegrityAuditReport(
            timestamp=datetime.now(UTC),
            is_valid=is_valid,
            violations=violations,
            stats=stats,
        )

    async def audit_economy_ledger(self) -> tuple[list[IntegrityViolation], dict[str, Any]]:
        """Validate sum(debits) == sum(credits) for each transaction and globally."""
        violations: list[IntegrityViolation] = []

        # Group by transaction_id and compare sum(DEBIT) vs sum(CREDIT)
        stmt = select(
            EconomyLedgerEntry.transaction_id,
            func.sum(
                case((EconomyLedgerEntry.direction == "DEBIT", EconomyLedgerEntry.amount), else_=0)
            ).label("total_debits"),
            func.sum(
                case((EconomyLedgerEntry.direction == "CREDIT", EconomyLedgerEntry.amount), else_=0)
            ).label("total_credits"),
        ).group_by(EconomyLedgerEntry.transaction_id)

        result = await self.session.execute(stmt)
        tx_rows = result.all()

        imbalanced_count = 0
        total_debits_global = 0
        total_credits_global = 0

        for row in tx_rows:
            tx_id, debits, credits = row[0], row[1] or 0, row[2] or 0
            total_debits_global += debits
            total_credits_global += credits
            if debits != credits:
                imbalanced_count += 1
                violations.append(
                    IntegrityViolation(
                        category="LEDGER_IMBALANCE",
                        severity="CRITICAL",
                        entity_id=tx_id,
                        details=f"Transaction {tx_id} ledger imbalance: debits={debits}, credits={credits}",
                        context={"transaction_id": tx_id, "debits": debits, "credits": credits},
                    )
                )

        stats = {
            "total_transactions_audited": len(tx_rows),
            "imbalanced_transactions": imbalanced_count,
            "total_debits_global": total_debits_global,
            "total_credits_global": total_credits_global,
        }
        return violations, stats

    async def audit_account_balances(self) -> tuple[list[IntegrityViolation], dict[str, Any]]:
        """Validate that no economy account has a negative balance."""
        violations: list[IntegrityViolation] = []

        stmt = select(EconomyAccount).where(
            EconomyAccount.account_type == "VIEWER", EconomyAccount.balance < 0
        )
        result = await self.session.execute(stmt)
        negative_accounts = list(result.scalars().all())

        for acc in negative_accounts:
            violations.append(
                IntegrityViolation(
                    category="NEGATIVE_BALANCE",
                    severity="CRITICAL",
                    entity_id=acc.id,
                    details=f"Account {acc.id} (viewer={acc.viewer_channel_id}) has negative balance {acc.balance}",
                    context={
                        "account_id": acc.id,
                        "creator_id": acc.creator_id,
                        "viewer_id": acc.viewer_channel_id,
                        "balance": acc.balance,
                    },
                )
            )

        total_stmt = select(func.count(EconomyAccount.id))
        total_res = await self.session.execute(total_stmt)
        total_accounts = total_res.scalar() or 0

        stats = {
            "total_accounts_audited": total_accounts,
            "negative_accounts_count": len(negative_accounts),
        }
        return violations, stats

    async def audit_store_inventory(self) -> tuple[list[IntegrityViolation], dict[str, Any]]:
        """Validate store items and viewer inventory consistency."""
        violations: list[IntegrityViolation] = []

        # Find orphaned inventory referencing non-existent store items
        stmt = (
            select(ViewerInventory)
            .outerjoin(StoreItem, ViewerInventory.item_id == StoreItem.id)
            .where(StoreItem.id.is_(None))
        )
        result = await self.session.execute(stmt)
        orphaned_inventory = list(result.scalars().all())

        for inv in orphaned_inventory:
            violations.append(
                IntegrityViolation(
                    category="ORPHANED_INVENTORY",
                    severity="ERROR",
                    entity_id=inv.id,
                    details=f"Inventory {inv.id} references non-existent store item {inv.item_id}",
                    context={"inventory_id": inv.id, "item_id": inv.item_id},
                )
            )

        stats = {
            "orphaned_inventory_count": len(orphaned_inventory),
        }
        return violations, stats

    async def audit_stale_stream_sessions(self) -> tuple[list[IntegrityViolation], dict[str, Any]]:
        """Detect live stream sessions that haven't received heartbeats in > 15 minutes."""
        violations: list[IntegrityViolation] = []
        cutoff = datetime.now(UTC) - timedelta(minutes=15)

        stmt = select(StreamSession).where(
            StreamSession.status == StreamStatus.ACTIVE.value,
            StreamSession.last_activity_at.is_not(None),
            StreamSession.last_activity_at < cutoff,
        )
        result = await self.session.execute(stmt)
        stale_sessions = list(result.scalars().all())

        for s in stale_sessions:
            violations.append(
                IntegrityViolation(
                    category="STALE_STREAM_SESSION",
                    severity="WARNING",
                    entity_id=s.id,
                    details=f"Stream session {s.id} marked LIVE but inactive since {s.last_activity_at}",
                    context={
                        "stream_id": s.id,
                        "creator_id": s.creator_id,
                        "video_id": s.youtube_video_id,
                    },
                )
            )

        stats = {
            "stale_live_sessions_count": len(stale_sessions),
        }
        return violations, stats

    async def execute_and_report_incidents(self) -> IntegrityAuditReport:
        """
        Execute full domain integrity audit and automatically pipeline any
        detected violations into the IncidentService, EventBus, and operational alerts.
        """
        report = await self.run_full_audit()
        if report.is_valid:
            return report

        from app.services.incidents import IncidentService

        incident_svc = IncidentService(self.session)
        for v in report.violations:
            service_name = (
                "ECONOMY_LEDGER"
                if "LEDGER" in v.category or "BALANCE" in v.category
                else "STORE_INVENTORY"
            )
            if "STREAM" in v.category:
                service_name = "STREAM_SUPERVISOR"

            try:
                await incident_svc.report_incident(
                    severity=v.severity,
                    service=service_name,
                    summary=f"[{v.category}] {v.details}",
                    creator_id=v.context.get("creator_id"),
                    stream_session_id=v.context.get("stream_id"),
                    action="Automated integrity pipeline triggered investigation",
                )
            except Exception as e:
                logger.error(f"Failed to report incident for violation {v.category}: {e}")

        return report
