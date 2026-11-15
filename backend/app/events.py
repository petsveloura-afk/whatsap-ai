import uuid, collections, datetime as dt
class Hub:
    """In-process per-user event hub (single worker). Events only reach the owning user."""
    def __init__(s): s.subs = collections.defaultdict(list)
    def add(s, uid, q, loop): s.subs[uid].append((q, loop))
    def remove(s, uid, q): s.subs[uid] = [x for x in s.subs[uid] if x[0] is not q]
    def publish(s, uid, type, payload, cid=None):
        ev = {"id": str(uuid.uuid4()), "type": type, "ts": dt.datetime.now(dt.timezone.utc).isoformat(),
              "user_id": uid, "payload": payload, "correlation_id": cid or str(uuid.uuid4())}
        for q, loop in list(s.subs[uid]): loop.call_soon_threadsafe(q.put_nowait, ev)
        return ev
hub = Hub()
STATS = {n: {"processed": 0, "errors": 0, "last_run": None, "total_ms": 0.0} for n in ("nlp_extraction", "filter_antispam", "matching")}
