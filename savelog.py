#!/usr/bin/env python3
import argparse
import requests
import sys
import getpass
import re

# Import dari config.py
try:
    from config import BASE_URL
except ImportError:
    print("Gagal import config.py. Pastikan file config.py ada dan bisa diakses.")
    sys.exit(1)

API_URL = BASE_URL  # langsung ambil dari config

def login(username=None, password=None):
    if not username:
        username = input("Username: ")
    if not password:
        password = getpass.getpass("Password: ")

    resp = requests.post(
        f"{API_URL}/login",
        data={"username": username, "password": password}
    )

    if resp.status_code == 200:
        token = resp.json()["access_token"]
        print("Login berhasil.")
        return token
    else:
        print("Login gagal:", resp.text)
        return None


def parse_expire(expire_str):
    """
    Parse string expire seperti:
    2m = 2 menit
    2h = 2 jam
    2d = 2 hari
    2M = 2 bulan (30 hari/bulan)
    2Y = 2 tahun (365 hari/tahun)
    """
    if not expire_str:
        return None

    pattern = r"^(\d+)([mhdMY])$"
    match = re.match(pattern, expire_str)
    if not match:
        print("Format expire salah! Contoh benar: 10m, 2h, 1d, 3M, 1Y")
        sys.exit(1)

    value = int(match.group(1))
    unit = match.group(2)

    if unit == "m":
        return value
    elif unit == "h":
        return value * 60
    elif unit == "d":
        return value * 60 * 24
    elif unit == "M":
        return value * 60 * 24 * 30
    elif unit == "Y":
        return value * 60 * 24 * 365

def save_log(token, content, filename=None, private=False, expire_minutes=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = {
        "content": content,
        "filename": filename,
        "private": private,
    }

    if expire_minutes:
        data["expire_minutes"] = expire_minutes

    resp = requests.post(f"{API_URL}/logs", json=data, headers=headers)
    if resp.status_code == 200:
        print("Log disimpan:", resp.json())
    else:
        print("Gagal menyimpan:", resp.text)

def main():
    parser = argparse.ArgumentParser(description="SaveLog CLI")
    parser.add_argument("-f", "--file", help="File yang akan diupload (jika tidak, baca dari stdin)")
    parser.add_argument("-n", "--filename", help="Nama file custom di server")
    parser.add_argument("--private", action="store_true", help="Buat log privat (butuh login)")
    parser.add_argument("-xp", "--expire", type=str, help="Waktu kedaluwarsa log. Contoh: 10m, 2h, 1d, 3M, 1Y")
    parser.add_argument("--login", action="store_true", help="Login sebelum upload")
    parser.add_argument("-u", "--username", help="Username untuk login")
    parser.add_argument("-p", "--password", help="Password untuk login")

    args = parser.parse_args()

    token = None
    if args.login or args.private:
        token = login(args.username, args.password)
        if not token:
            sys.exit(1)

    if args.file:
        with open(args.file, "r") as f:
            content = f.read()
    else:
        content = sys.stdin.read()

    expire_minutes = parse_expire(args.expire) if args.expire else None

    save_log(token, content, filename=args.filename, private=args.private, expire_minutes=expire_minutes)

if __name__ == "__main__":
    main()
