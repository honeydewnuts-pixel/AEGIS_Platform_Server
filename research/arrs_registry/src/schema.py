SCHEMA_VERSION = "1.0.0"
LIFECYCLE_STATES = frozenset({
    "DISCOVERED", "SCREENED", "VALIDATED", "DEMO_ELIGIBLE", "DEMO_QUALIFIED",
    "APPROVED", "DEGRADED", "SUSPENDED", "REJECTED", "RETIRED",
})
EVAL_STATUSES = frozenset({"PASS", "FAIL", "INSUFFICIENT_EVIDENCE", "NOT_RUN"})
# Research may never set these True via registry APIs
AUTH_FIELDS = ("production_authorized", "execution_authorized")
