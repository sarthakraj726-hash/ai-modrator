# Incident Runbook: Economy Ledger Imbalance & Accounting Integrity Violation

## Severity
- **CRITICAL**: Threatens virtual coin accounting integrity and double-entry invariants.

## Core Invariant
$$\sum \text{Debits} == \sum \text{Credits} \quad \text{for every transaction and globally.}$$
$$\text{Account.balance} \ge 0 \quad \text{for all viewer and creator accounts.}$$

## Symptoms
- System alert: `[CRITICAL] ECONOMY LEDGER IMBALANCE DETECTED`.
- `IntegrityCheckService` identifies non-zero delta in `audit_economy_ledger()`.
- Negative balance detected in `audit_account_balances()`.

## Immediate Mitigation Steps
1. **Quarantine Economy Mutations (if active corruptor)**:
   - Toggle feature flag `feature.economy.mint_enabled: false` via database or environment flag.
2. **Execute Diagnostic Ledger Audit**:
   - Query `/api/v1/dashboard/economy` to inspect imbalanced transaction IDs.
   - Run manual inspection:
     ```sql
     SELECT transaction_id, 
            sum(case when direction = 'DEBIT' then amount else 0 end) as debits,
            sum(case when direction = 'CREDIT' then amount else 0 end) as credits
     FROM economy_ledger_entries
     GROUP BY transaction_id
     HAVING sum(case when direction = 'DEBIT' then amount else 0 end) != 
            sum(case when direction = 'CREDIT' then amount else 0 end);
     ```
3. **Audit Negative Balances**:
   - Query accounts with balance < 0:
     ```sql
     SELECT id, creator_id, viewer_channel_id, balance 
     FROM economy_accounts 
     WHERE balance < 0;
     ```
4. **Post Compensating Journal Entry**:
   - Never directly modify past immutable ledger rows.
   - Post an explicit compensating adjustment transaction (`ADJUSTMENT`) to restore mathematical balance.

## Prevention & Resolution
- Verify that every code path mutates balances exclusively through `EconomyService` with row locking (`for_update=True`).
