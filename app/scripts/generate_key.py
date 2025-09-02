#!/usr/bin/env python3.11

import argparse
import secrets
import string


def gen_app_id(length: int = 10) -> str:
    """Generate a random app_id with the given length in digits."""
    digits = string.digits
    return "".join(secrets.choice(digits) for _ in range(length))


def gen_hex_key(length_bytes: int = 16) -> str:
    """Generate a random hex key with the given length in bytes."""
    return secrets.token_hex(length_bytes)


def main():
    parser = argparse.ArgumentParser(description="Generate app_id, app_key, app_secret")
    parser.add_argument(
        "--id-length",
        type=int,
        default=10,
        help="app_id length in digits (default: 10)",
    )
    parser.add_argument(
        "--key-bytes",
        type=int,
        default=16,
        help="app_key length in bytes (default: 16 -> 32 hex chars)",
    )
    parser.add_argument(
        "--secret-bytes",
        type=int,
        default=32,
        help="app_secret length in bytes (default: 32 -> 64 hex chars)",
    )
    args = parser.parse_args()

    app_id = gen_app_id(args.id_length)
    app_key = gen_hex_key(args.key_bytes)
    app_secret = gen_hex_key(args.secret_bytes)

    print("Generated credentials:")
    print(f"APP_ID     = {app_id}")
    print(f"APP_KEY    = {app_key}")
    print(f"APP_SECRET = {app_secret}")


if __name__ == "__main__":
    main()
