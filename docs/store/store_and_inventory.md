# Creator Store & Viewer Inventory Architecture

## Store Engine Overview
The creator store enables stream viewers to redeem accumulated virtual coins for digital perks, badges, shoutouts, or sound effects.

### Entity Schema
- **`StoreItem`**:
  - `id`: UUID
  - `creator_id`: Foreign key to `creators.id`
  - `name`: Unique within creator scope
  - `description`: Informational text
  - `price`: Virtual coins required
  - `stock`: Finite inventory (e.g. 10) or `-1` for unlimited
  - `max_per_user`: Max quantity a single viewer can own (or `-1` for unlimited)
  - `enabled`: Boolean toggle
- **`ViewerInventory`**:
  - `creator_id`: Creator scope
  - `viewer_channel_id`: Viewer ID
  - `item_id`: Store item reference
  - `quantity`: Current owned quantity

---

## Transactional Purchase Pipeline

When a viewer types `!buy <item_name>`:
1. **Resolution**: Match `StoreItem` within `creator_id` scope.
2. **Stock Verification**: Reject if `item.stock == 0` (`OUT_OF_STOCK`).
3. **Limit Verification**: Reject if `item.max_per_user > 0` and viewer already owns that limit.
4. **Ledger Settlement**: Call `EconomyService.spend(creator_id, viewer_id, item.price)`.
   - Rejects if viewer balance < item.price (`INSUFFICIENT_FUNDS`).
   - Mints double-entry transaction (`VIEWER -price`, `SYSTEM_SINK +price`).
5. **Stock Decrement**: Decrement `stock -= 1` if finite.
6. **Inventory Grant**: Grant or increment `ViewerInventory.quantity += 1`.
7. **Engagement Audit**: Increment `ViewerEngagement.store_purchases`.
