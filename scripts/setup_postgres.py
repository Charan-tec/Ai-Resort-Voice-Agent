import os
import subprocess
import sys
import time
import zipfile

PG_VERSION = "16.6-1"
ZIP_URL = f"https://get.enterprisedb.com/postgresql/postgresql-{PG_VERSION}-windows-x64-binaries.zip"
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".pg16"))
PGSQL_DIR = os.path.join(BASE_DIR, "pgsql")
DATA_DIR = os.path.join(BASE_DIR, "data")
PORT = 5433


def download_and_extract():
    if os.path.exists(os.path.join(PGSQL_DIR, "bin", "postgres.exe")):
        print(f"PostgreSQL 16 binaries already exist in {PGSQL_DIR}")
        return

    os.makedirs(BASE_DIR, exist_ok=True)
    zip_path = os.path.join(BASE_DIR, "pg16.zip")

    # If partial or empty zip exists, remove it
    if os.path.exists(zip_path) and os.path.getsize(zip_path) < 1000000:
        os.remove(zip_path)

    if not os.path.exists(zip_path):
        print(f"Downloading PostgreSQL 16 binaries via curl from {ZIP_URL}...")
        # Use curl with retry and resume
        cmd = ["curl.exe", "-L", "-C", "-", "-o", zip_path, ZIP_URL]
        res = subprocess.run(cmd)
        if res.returncode != 0 or not os.path.exists(zip_path) or os.path.getsize(zip_path) < 1000000:
            print(f"Curl download failed with code {res.returncode}")
            sys.exit(1)

    print("Download complete. Extracting required components (bin, lib, share)...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            # Skip heavy debug symbols, docs, and C headers
            if "symbols" in member.filename or "doc" in member.filename or "include" in member.filename:
                continue
            if member.filename.startswith("pgsql/bin/") or member.filename.startswith("pgsql/lib/") or member.filename.startswith("pgsql/share/"):
                zf.extract(member, BASE_DIR)

    # Delete zip archive to free up disk space
    if os.path.exists(zip_path):
        os.remove(zip_path)
    print("PostgreSQL 16 binaries extracted successfully.")


def init_database():
    initdb = os.path.join(PGSQL_DIR, "bin", "initdb.exe")
    if not os.path.exists(DATA_DIR):
        print(f"Initializing PostgreSQL database cluster at {DATA_DIR}...")
        cmd = [initdb, "-D", DATA_DIR, "-U", "postgres", "-A", "trust", "--no-locale", "--encoding=UTF8"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"initdb failed: {res.stderr}")
            sys.exit(1)
        print("Database cluster initialized.")


def start_server():
    pg_ctl = os.path.join(PGSQL_DIR, "bin", "pg_ctl.exe")
    log_file = os.path.join(BASE_DIR, "server.log")

    # Check if already running
    status_cmd = [pg_ctl, "-D", DATA_DIR, "status"]
    status_res = subprocess.run(status_cmd, capture_output=True, text=True)
    if "server is running" in status_res.stdout:
        print(f"PostgreSQL 16 is already running on port {PORT}.")
        return

    print(f"Starting PostgreSQL 16 on port {PORT}...")
    start_cmd = [
        pg_ctl, "-D", DATA_DIR, "-l", log_file, "-o", f"-p {PORT}", "start"
    ]
    res = subprocess.run(start_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"pg_ctl start failed: {res.stderr}")
        sys.exit(1)

    time.sleep(2)
    print(f"PostgreSQL 16 server successfully started on port {PORT}.")


def create_test_db():
    createdb = os.path.join(PGSQL_DIR, "bin", "createdb.exe")
    cmd = [createdb, "-h", "127.0.0.1", "-p", str(PORT), "-U", "postgres", "resort_voice_test"]
    subprocess.run(cmd, capture_output=True, text=True)

    psql = os.path.join(PGSQL_DIR, "bin", "psql.exe")
    ext_cmd = [
        psql, "-h", "127.0.0.1", "-p", str(PORT), "-U", "postgres", "-d", "resort_voice_test",
        "-c", "CREATE EXTENSION IF NOT EXISTS btree_gist;"
    ]
    res = subprocess.run(ext_cmd, capture_output=True, text=True)
    print("Database 'resort_voice_test' created and btree_gist extension enabled.")
    print(res.stdout)


if __name__ == "__main__":
    download_and_extract()
    init_database()
    start_server()
    create_test_db()
