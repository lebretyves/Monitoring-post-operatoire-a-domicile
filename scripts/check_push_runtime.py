from __future__ import annotations

import os
import urllib.request

from app.settings import load_settings


def main() -> None:
    settings = load_settings()
    print(f"env ENABLE_WEBPUSH={os.getenv('ENABLE_WEBPUSH')}")
    print(f"env VAPID_PUBLIC_KEY={os.getenv('VAPID_PUBLIC_KEY')}")
    print(f"settings.enable_webpush={settings.enable_webpush}")
    print(f"settings.vapid_public_key={settings.vapid_public_key}")
    print(
        "http /api/push/config="
        + urllib.request.urlopen("http://127.0.0.1:8000/api/push/config", timeout=3).read().decode()
    )


if __name__ == "__main__":
    main()
