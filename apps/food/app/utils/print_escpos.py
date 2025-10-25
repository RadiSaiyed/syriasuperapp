from typing import List, Optional
import os


def print_ticket(lines: List[str], *, device: Optional[str] = None) -> None:
    """Best-effort ESC/POS printing.

    Tries to use python-escpos if available and a device/environment is configured.
    Otherwise, no-ops. This should never break request handling.
    """
    try:
        device = device or os.getenv("ESCPOS_DEVICE", "").strip()
        if not device:
            return
        try:
            from escpos.printer import File  # type: ignore
        except Exception:
            # Fallback: write text into device path if possible
            try:
                with open(device, "a", encoding="utf-8", errors="ignore") as f:
                    f.write("\n".join(lines) + "\n\n")
            except Exception:
                pass
            return
        try:
            p = File(device)
            for ln in lines:
                p.text(ln + "\n")
            p.cut()
            try:
                p.close()
            except Exception:
                pass
        except Exception:
            pass
    except Exception:
        pass

