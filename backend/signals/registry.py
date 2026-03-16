from signals.ma_crossover import compute as compute_ma_crossover
from signals.rsi_divergence import compute_rsi_divergence

# Registry of all signals.
# Each entry declares the compute function, persistence target, API prefix,
# schedule cadence, and required input arrays.
# Adding a new signal requires only:
#   1. A new signals/<name>.py with the compute function.
#   2. A new entry here.
# tasks.py and main.py iterate this registry — no new boilerplate needed there.

SIGNAL_REGISTRY = {
    "ma_crossover": {
        "compute_fn": compute_ma_crossover,
        "db_table": "ma_crossover_signals",
        "route_prefix": "/signals/ma-crossover",
        "schedule": "daily_after_close",
        "required_inputs": ["closes"],
    },
    "rsi_divergence": {
        "compute_fn": compute_rsi_divergence,
        "db_table": "rsi_divergence_signals",
        "route_prefix": "/signals/rsi-divergence",
        "schedule": "daily_after_close",
        "required_inputs": ["closes", "highs", "lows", "rsi_series"],
    },
}
