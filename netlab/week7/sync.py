#!/usr/bin/env python3
"""Reconcile the Week 7 lab API with a YAML intent file."""

import argparse
import random
import re
import sys
import time
from dataclasses import dataclass
from ipaddress import ip_network
from pathlib import Path
from uuid import uuid4

import requests
import yaml

from inventory import API, Client

VLANS = "/api/v1/vlans"
ACL_ENTRIES = "/api/v1/acl/entries"
REQUEST_ERRORS = (requests.exceptions.RequestException, RuntimeError)


@dataclass(frozen=True)
class Change:
    method: str
    path: str
    description: str
    body: dict | None = None


class SyncClient(Client):
    def read_state(self):
        vlans = self.get_page(f"{API}{VLANS}").json()["items"]
        acl_entries = self.get_page(f"{API}{ACL_ENTRIES}").json()["items"]
        return vlans, acl_entries

    def apply(self, change):
        headers = {}
        if change.method == "POST":
            headers["Idempotency-Key"] = str(uuid4())
        elif change.method not in ("PUT", "DELETE"):
            raise ValueError(f"Cannot safely retry {change.method}")

        url = f"{API}{change.path}"
        failures = 0
        while True:
            headers["Authorization"] = f"Bearer {self.token}"
            self.requests += 1
            try:
                response = requests.request(
                    change.method, url, headers=headers, json=change.body, timeout=5,
                )
            except (requests.ConnectionError, requests.Timeout) as exc:
                failure = type(exc).__name__
            else:
                status = response.status_code
                if 200 <= status < 300 or (change.method == "DELETE" and status == 404):
                    return
                if status == 401:
                    print("401 Unauthorized. Logging in again.")
                    self.login()
                    continue
                if status == 429:
                    wait = int(response.headers["Retry-After"])
                    print(f"429 Too Many Requests. Retrying in {wait}s.")
                    time.sleep(wait)
                    continue
                if status != 503:
                    response.raise_for_status()
                    raise RuntimeError(f"Unexpected HTTP status {status} for {url}")
                failure = "503 Service Unavailable"

            failures += 1
            if failures == 6:
                raise RuntimeError(f"{failure} after {failures} attempts to {change.description.lower()}")
            wait = 2 ** (failures - 1) + random.uniform(0, 0.25)
            print(f"{failure}. Retrying in {wait:.2f}s.")
            time.sleep(wait)


def acl_fields(rule):
    """Compare desired and returned ACLs independently of their API IDs."""
    return {
        "action": rule["action"],
        "src": rule["src"],
        "dst": rule["dst"],
        "protocol": rule.get("protocol", "any"),
        "port": rule.get("port"),
        "description": rule.get("description", ""),
    }


def read_intent(path):
    intent = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(intent, dict) or any(not isinstance(intent.get(key), list) for key in ("vlans", "acl")):
        raise ValueError("Intent must contain vlans and acl lists.")

    vlans = {}
    for item in intent["vlans"]:
        if not isinstance(item, dict):
            raise ValueError("Each VLAN must have an ID and name.")
        vlan_id, name = item.get("id"), item.get("name")
        if type(vlan_id) is not int or not 2 <= vlan_id <= 4094:
            raise ValueError("VLAN IDs must be integers from 2 to 4094. VLAN 1 is reserved.")
        if vlan_id in vlans:
            raise ValueError(f"Duplicate VLAN ID {vlan_id}.")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", name):
            raise ValueError(f"Invalid name for VLAN {vlan_id}.")
        vlans[vlan_id] = name

    acl_entries = []
    for index, item in enumerate(intent["acl"], 1):
        if not isinstance(item, dict) or not {"action", "src", "dst"} <= item.keys():
            raise ValueError(f"ACL entry {index} requires action, src, and dst.")
        rule = acl_fields(item)
        if rule["action"] not in ("permit", "deny") or rule["protocol"] not in ("any", "tcp", "udp", "icmp"):
            raise ValueError(f"Invalid action or protocol in ACL entry {index}.")
        for field in ("src", "dst"):
            if not isinstance(rule[field], str):
                raise ValueError(f"Invalid {field} network in ACL entry {index}.")
            ip_network(rule[field])
        port = rule["port"]
        if port is not None and (type(port) is not int or not 1 <= port <= 65535 or rule["protocol"] not in ("tcp", "udp")):
            raise ValueError(f"Invalid port in ACL entry {index}. Ports require TCP or UDP.")
        if not isinstance(rule["description"], str):
            raise ValueError(f"Invalid description in ACL entry {index}.")
        acl_entries.append(rule)
    return vlans, acl_entries


def describe_acl(rule):
    protocol = rule["protocol"]
    if rule.get("port") is not None:
        protocol = f"{protocol}/{rule['port']}"
    label = f"{rule['action']} {rule['src']} to {rule['dst']} ({protocol})"
    if rule.get("description"):
        label += f" [{rule['description']}]"
    return label


def make_plan(current, desired):
    current_vlans, current_acl = current
    desired_vlans, desired_acl = desired
    names = {vlan["id"]: vlan["name"] for vlan in current_vlans if vlan["id"] != 1}
    changes = []
    for vlan_id, name in sorted(desired_vlans.items()):
        old_name = names.get(vlan_id)
        if old_name == name:
            continue
        if old_name is None:
            description = f"Create VLAN {vlan_id} ({name})"
        else:
            description = f"Change VLAN {vlan_id} from {old_name} to {name}"
        changes.append(Change("PUT", f"{VLANS}/{vlan_id}", description, {"name": name}))

    missing_acl = desired_acl.copy()
    extra_acl = []
    for entry in current_acl:
        rule = acl_fields(entry)
        if rule in missing_acl:
            missing_acl.remove(rule)
        else:
            extra_acl.append(entry)

    for rule in missing_acl:
        changes.append(Change("POST", ACL_ENTRIES, f"Create ACL {describe_acl(rule)}", rule))
    for entry in extra_acl:
        entry_id = entry["id"]
        label = describe_acl(acl_fields(entry))
        changes.append(Change("DELETE", f"{ACL_ENTRIES}/{entry_id}", f"Delete ACL {entry_id} ({label})"))
    for vlan_id in sorted(names.keys() - desired_vlans.keys()):
        changes.append(Change("DELETE", f"{VLANS}/{vlan_id}", f"Delete VLAN {vlan_id} ({names[vlan_id]})"))
    return changes


def print_plan(plan):
    if not plan:
        print("Plan is empty. No changes needed.")
        return
    print(f"Plan has {len(plan)} changes.")
    for change in plan:
        print(f"  {change.description}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("intent", type=Path, help="Path to intent.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Show the plan without applying it")
    args = parser.parse_args()

    desired = read_intent(args.intent)
    client = SyncClient()
    plan = make_plan(client.read_state(), desired)
    print_plan(plan)
    if args.dry_run:
        print("Dry run. No configuration writes sent.")
        return 0

    if plan:
        try:
            for change in plan:
                print(change.description)
                client.apply(change)
        except REQUEST_ERRORS as exc:
            print(f"Apply stopped during {change.description.lower()}. {exc}", file=sys.stderr)
        remaining = make_plan(client.read_state(), desired)
        if remaining:
            print("Verification failed. API does not match intent.")
            print_plan(remaining)
            return 1

    print("Verified. API matches intent.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, yaml.YAMLError, *REQUEST_ERRORS) as exc:
        sys.exit(f"Sync failed. {exc}")
