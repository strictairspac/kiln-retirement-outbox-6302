from uuid import uuid4

from sqlalchemy import text


class DrillAbort(Exception):
    pass


class RetirementTables:
    def __init__(self, db):
        self.db = db
        suffix = uuid4().hex[:12]
        self.assets = f"oven_asset_{suffix}"
        self.outbox = f"oven_outbox_{suffix}"
        self.receipts = f"oven_receipt_{suffix}"

    def create(self, requests):
        for table, fields in (
            (self.assets, "asset text PRIMARY KEY, certificate text UNIQUE"),
            (self.outbox, f"""
                event_key text PRIMARY KEY, asset text NOT NULL UNIQUE REFERENCES {self.assets},
                interrupt_ack boolean NOT NULL, attempts integer NOT NULL DEFAULT 0,
                lease_until integer NOT NULL DEFAULT 0, acknowledged boolean NOT NULL DEFAULT false
            """),
            (self.receipts, f"event_key text PRIMARY KEY REFERENCES {self.outbox}, archived_at integer NOT NULL"),
        ):
            self.db.execute(text(f"CREATE TEMP TABLE {table} ({fields}) ON COMMIT DROP"))
        self.db.execute(text(f"INSERT INTO {self.assets} (asset) VALUES (:asset)"), [
            {"asset": request.asset} for request in requests
        ])

    def retire(self, request):
        try:
            with self.db.begin_nested():
                self.db.execute(text(f"""
                    UPDATE {self.assets} SET certificate = :certificate WHERE asset = :asset
                """), {"asset": request.asset, "certificate": request.certificate})
                if request.failed_stage == "before_enqueue":
                    raise DrillAbort
                self.db.execute(text(f"""
                    INSERT INTO {self.outbox} (event_key, asset, interrupt_ack)
                    VALUES (:certificate, :asset, :interrupt_ack)
                """), {
                    "certificate": request.certificate,
                    "asset": request.asset,
                    "interrupt_ack": request.failed_stage == "after_receipt",
                })
        except DrillAbort:
            return

    def result_rows(self):
        return self.db.execute(text(f"""
            SELECT a.asset, a.certificate, o.attempts, o.acknowledged, r.archived_at
            FROM {self.assets} AS a
            LEFT JOIN {self.outbox} AS o ON a.asset = o.asset
            LEFT JOIN {self.receipts} AS r ON o.event_key = r.event_key
            ORDER BY a.asset COLLATE "C"
        """)).mappings().all()
