"""Phase 0 precondition: verify the Gmail OAuth token's granted scopes
WITHOUT sending anything. Pure introspection via Google's tokeninfo
endpoint (read-only) -- does not call any Gmail/Calendar API method.

Reads creds by name only from ~/ultra-csm-live-creds.env; never prints
credential values, only booleans/lengths/scope strings/HTTP status.
"""
import json
import subprocess
import sys

CREDS_PATH = "/Users/owieschon/ultra-csm-live-creds.env"


def _read_env():
    env = {}
    with open(CREDS_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k] = v
    return env


def main():
    env = _read_env()
    client_id = env["ULTRA_CSM_GMAIL_OAUTH_CLIENT_ID"]
    client_secret = env["ULTRA_CSM_GMAIL_OAUTH_CLIENT_SECRET"]
    refresh_token = env["ULTRA_CSM_GMAIL_OAUTH_REFRESH_TOKEN"]

    # Token exchange via curl (system trust store -- avoids the venv SSL
    # trust-store gap Program 9 also hit on Python 3.14).
    token_resp = subprocess.run(
        [
            "curl", "-s", "-X", "POST", "https://oauth2.googleapis.com/token",
            "-d", f"client_id={client_id}",
            "-d", f"client_secret={client_secret}",
            "-d", f"refresh_token={refresh_token}",
            "-d", "grant_type=refresh_token",
        ],
        capture_output=True, text=True, timeout=30,
    )
    data = json.loads(token_resp.stdout)
    access_token = data.get("access_token")
    if not access_token:
        print("TOKEN EXCHANGE FAILED:", {k: v for k, v in data.items() if k != "access_token"})
        sys.exit(1)
    print("token exchange: OK")

    info_resp = subprocess.run(
        [
            "curl", "-s", "-o", "/tmp/act2_tokeninfo.json", "-w", "%{http_code}",
            f"https://oauth2.googleapis.com/tokeninfo?access_token={access_token}",
        ],
        capture_output=True, text=True, timeout=30,
    )
    status = info_resp.stdout.strip()
    print("tokeninfo HTTP status:", status)
    with open("/tmp/act2_tokeninfo.json") as f:
        info = json.load(f)
    scopes = info.get("scope", "").split()
    print("scopes granted:")
    for s in scopes:
        print(" -", s)
    print("expires_in:", info.get("expires_in"))

    send_scope = "https://www.googleapis.com/auth/gmail.send"
    has_send = send_scope in scopes or "https://mail.google.com/" in scopes
    print("gmail.send scope present:", has_send)


if __name__ == "__main__":
    main()
