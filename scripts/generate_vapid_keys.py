from __future__ import annotations

import base64

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid01


def main() -> None:
    vapid = Vapid01()
    vapid.generate_keys()
    public_key = vapid.public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    public_key_b64 = base64.urlsafe_b64encode(public_key).decode().rstrip("=")
    private_pem = vapid.private_pem().decode().strip()
    private_pem_env = private_pem.replace("\n", "\\n")

    print(f"VAPID_PUBLIC_KEY={public_key_b64}")
    print(f"VAPID_PRIVATE_KEY={private_pem_env}")


if __name__ == "__main__":
    main()
