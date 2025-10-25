import os
from functools import lru_cache


@lru_cache(maxsize=1)
def ensure_loaded() -> None:
    """Load central env file once, if configured.

    Priority:
    1) SUPERAPP_ENV_FILE path
    2) /etc/superapp/superapp.env
    3) ops/secrets/superapp.secrets.env (relative to CWD)
    Does not override environment variables already set.
    """
    candidates = [
        os.getenv("SUPERAPP_ENV_FILE", ""),
        "/etc/superapp/superapp.env",
        os.path.join("ops", "secrets", "superapp.secrets.env"),
    ]
    for p in candidates:
        if not p:
            continue
        try:
            if os.path.isfile(p):
                _load_env_file(p)
                return
        except Exception:
            continue


def _load_env_file(path: str) -> None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        # Silent fallback; environment remains unchanged
        pass

