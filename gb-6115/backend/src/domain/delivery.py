from sqlalchemy import text


def take_lease(tables, now, ttl):
    db, outbox = tables.db, tables.outbox
    with db.begin_nested():
        row = db.execute(text(f"""
            WITH candidate AS (
                SELECT event_key FROM {outbox}
                WHERE NOT acknowledged AND lease_until <= :now
                ORDER BY lease_until, event_key COLLATE "C"
                LIMIT 1 FOR UPDATE SKIP LOCKED
            )
            UPDATE {outbox} AS events
            SET lease_until = :until, attempts = attempts + 1
            FROM candidate WHERE events.event_key = candidate.event_key
            RETURNING events.event_key, events.attempts, events.interrupt_ack
        """), {"now": now, "until": now + ttl}).mappings().one_or_none()
    return row


def insert_receipt(tables, event_key, now):
    with tables.db.begin_nested():
        return tables.db.execute(text(f"""
            INSERT INTO {tables.receipts} (event_key, archived_at) VALUES (:event_key, :now)
            ON CONFLICT (event_key) DO NOTHING
            RETURNING event_key
        """), {"event_key": event_key, "now": now}).scalar_one_or_none()


def acknowledge(tables, lease, now):
    with tables.db.begin_nested():
        return tables.db.execute(text(f"""
            UPDATE {tables.outbox} SET acknowledged = true
            WHERE event_key = :event_key AND attempts = :version
              AND NOT acknowledged AND lease_until > :now
            RETURNING event_key
        """), {
            "event_key": lease["event_key"], "version": lease["attempts"], "now": now,
        }).scalar_one_or_none()


def next_expiry(tables):
    return tables.db.execute(text(f"""
        SELECT min(lease_until) FROM {tables.outbox} WHERE NOT acknowledged
    """)).scalar_one()


def replay(tables, observe_until, ttl):
    suppressed = 0
    now = 0
    while now <= observe_until:
        while lease := take_lease(tables, now, ttl):
            if insert_receipt(tables, lease["event_key"], now) is None:
                suppressed += 1
            if lease["attempts"] == 1 and lease["interrupt_ack"]:
                continue
            if acknowledge(tables, lease, now) is None:
                raise ValueError("租约已换代或过期，无法确认归档")
        expiry = next_expiry(tables)
        if expiry is None:
            break
        if expiry <= now:
            raise ValueError("隔离演练中发现未领取的到期事件")
        now = expiry
    return suppressed
