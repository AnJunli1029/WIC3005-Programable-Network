#!/usr/bin/env python3
"""Week 7 lab, Steps 5 and 6: read EVERY device from the lab API, however it misbehaves.

Run it in the client container:
    export LAB_USERNAME=netops LAB_PASSWORD='YOUR_LAB_PASSWORD'   # in the environment, never in this file
    python3 inventory.py

It writes devices.json and prints how many devices each site has.
"""
import json
import os
import random
import sys
import time
from collections import Counter

import requests

API = os.environ.get("LAB_API_URL", "http://api:8000")


class Client:
    """A logged-in session with the lab API."""

    def __init__(self):
        self.token = None
        self.requests = 0  # how many HTTP requests this client sent, retries included

    def login(self):
        """Get a fresh token, with the username and password from the environment."""
        try:
            user, password = os.environ["LAB_USERNAME"], os.environ["LAB_PASSWORD"]
        except KeyError:
            sys.exit("Set LAB_USERNAME and LAB_PASSWORD in the environment first.")
        self.requests += 1
        r = requests.post(f"{API}/api/v1/auth/token", json={"username": user, "password": password}, timeout=5)
        r.raise_for_status()
        self.token = r.json()["token"]
        print(f"logged in as {user}")

    def get_page(self, url):
        """Return a successful page, renewing the token or retrying as needed."""
        if self.token is None:
            self.login()

        failures = 0
        while True:
            self.requests += 1
            try:
                r = requests.get(url, headers={"Authorization": f"Bearer {self.token}"}, timeout=5)
            except (requests.ConnectionError, requests.Timeout) as exc:
                failure = type(exc).__name__
            else:
                status = r.status_code
                if 200 <= status < 300:
                    return r
                if status == 401:
                    print("401 Unauthorized. Logging in again.")
                    self.login()
                    continue
                if status == 429:
                    wait = int(r.headers["Retry-After"])
                    print(f"429 Too Many Requests. Retrying in {wait}s.")
                    time.sleep(wait)
                    continue
                if status != 503:
                    r.raise_for_status()
                    raise RuntimeError(f"Unexpected HTTP status {status} for {url}")
                failure = "503 Service Unavailable"

            failures += 1
            if failures == 6:
                raise RuntimeError(f"{failure} after {failures} attempts for {url}")
            wait = 2 ** (failures - 1) + random.uniform(0, 0.25)
            print(f"{failure}. Retrying in {wait:.2f}s.")
            time.sleep(wait)

    def get_all(self, url):
        """Return all devices and the first page's X-Total-Count header."""
        items, total = [], None
        while url is not None:
            response = self.get_page(url)
            if total is None:
                total = response.headers["X-Total-Count"]
            page = response.json()
            items.extend(page["items"])
            url = page["next"]
        return items, total


def main():
    c = Client()
    devices, total = c.get_all(f"{API}/api/v1/devices?limit=10")
    if not devices:
        sys.exit("The API returned no devices.")
    with open("devices.json", "w") as f:
        json.dump(devices, f, indent=2)
    print(f"{len(devices)} devices read (the API says {total}), in {c.requests} requests; saved devices.json")
    for site, n in sorted(Counter(d["site"] for d in devices).items()):
        print(f"  {site}: {n}")
    if total is None or len(devices) != int(total):
        sys.exit("The count doesn't match X-Total-Count: some devices are missing.")


if __name__ == "__main__":
    main()
