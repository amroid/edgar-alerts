#!/usr/bin/env python3
"""Check EDGAR for new filings from a specific CIK and send Pushover alerts."""

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

CIK = "0002045724"  # Situational Awareness LP
STATE_FILE = Path("last_seen.txt")
USER_AGENT = os.environ["EDGAR_USER_AGENT"]
PUSHOVER_TOKEN = os.environ["PUSHOVER_TOKEN"]
PUSHOVER_USER = os.environ["PUSHOVER_USER"]


def fetch_filings():
    url = f"https://data.sec.gov/submissions/CIK{CIK}.json"
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(req, timeout=30) as resp:
        return json.load(resp)


def parse_recent(data):
    r = data["filings"]["recent"]
    return list(zip(r["accessionNumber"], r["form"], r["filingDate"], r["primaryDocument"]))


def load_seen():
    return set(STATE_FILE.read_text().splitlines()) if STATE_FILE.exists() else set()


def save_seen(accessions):
    STATE_FILE.write_text("\n".join(sorted(accessions)) + "\n")


def edgar_url(accession, primary_doc):
    acc_nodash = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{int(CIK)}/{acc_nodash}/{primary_doc}"


def push(title, message, url):
    payload = urlencode({
        "token": PUSHOVER_TOKEN,
        "user": PUSHOVER_USER,
        "title": title,
        "message": message,
        "url": url,
        "url_title": "Open on EDGAR",
        "priority": 0,
    }).encode()
    req = Request("https://api.pushover.net/1/messages.json", data=payload)
    with urlopen(req, timeout=30) as resp:
        if resp.status != 200:
            raise RuntimeError(f"Pushover returned {resp.status}")


def main():
    seen = load_seen()
    data = fetch_filings()
    company = data.get("name", "Unknown")
    filings = parse_recent(data)
    current = {a for a, _, _, _ in filings}

    if not seen:
        save_seen(current)
        print(f"First run: baselined {len(current)} filings, no alerts sent.")
        return

    new = [f for f in filings if f[0] not in seen]
    if not new:
        print("No new filings.")
        return

    for accession, form, date, primary_doc in new:
        push(
            title=f"New {form} from {company}",
            message=f"Filed {date}\nAccession: {accession}",
            url=edgar_url(accession, primary_doc),
        )
        print(f"Alerted: {accession} ({form}, {date})", file=sys.stderr)

    save_seen(current)


if __name__ == "__main__":
    main()
