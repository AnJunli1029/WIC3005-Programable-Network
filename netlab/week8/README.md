# Lab

1. Why is an interface's `type` an identityref, not an enumeration? What can IANA do without changing `ietf-interfaces`?
	- Answer: An enumeration lists its allowed values in the type definition. An `identityref` lets other modules define new values based on `interface-type`. IANA can add new interface types to `iana-if-type` without editing `ietf-interfaces`.
	
2. Why is IPv4 added to interfaces by a separate module's `augment`, rather than written into `ietf-interfaces`?
	- Answer: The base interface model also works for interfaces that do not carry IP. The `ietf-ip` module uses `augment` to add IPv4 settings under each interface. This lets the two modules be maintained separately.
	
3. `interfaces.json` is valid as configuration and invalid as a device's full data. What's missing, and who supplies it?
	- Answer: The file is missing required read-only state for `eth1` and `lo0`, including `admin-status`, `oper-status`, `if-index`, and `statistics/discontinuity-time`. The device supplies these values in `<operational>`.
	
4. Which mistakes does `pyang --strict` find, and which only `yanglint`? Why can't pyang find the second kind?
	- Answer: `pyang --strict` checks the YANG model for errors such as a missing semicolon. `yanglint` checks actual data against the model. It caught a prefix length of `33` and a reference to VLAN `20`, which did not exist. Those errors only show up when the data is loaded.
	
5. Which breaking change did `--check-update-from` miss? What would have caught it?
	- Answer: It missed the change from `8..63` to `12..63` for `passphrase`. Running `yanglint -t config` against both versions with the same Wi-Fi configuration would catch it. A 10-character passphrase passes with the old model and fails with the new one.
---
# Assignment

1. Which rules could you **not** express in YANG, or only awkwardly? Where should they live instead, and why there? (Try `10.NN.40.5/24` — a prefix with host bits set — against your model, and against the lab API.)
	- Answer: My model checks the IPv4 prefix format and the allowed block. It accepted `10.16.40.5/24` even though its host bits are set. The Week 7 API rejected it with HTTP `422`. I would keep this check in the API, where an IP parser can check whether the address is the start of the network before applying the rule. My `sync.py` sends this prefix as `10.16.40.0/24`.
	
2. Your address rule is about your own block. How would one model, shared by the whole class, express "addresses from the owner's block"?
	-  Answer: A shared model could use an `owner-octet` value that the server sets from the logged-in account. A YANG `must` rule could check that both `src` and `dst` start with `10.<owner-octet>.` and that the prefix length is at least `/16`.
	
3. In Week 7's lab API, which data would be `config false` if it had a YANG model? Name three things.	
	- Answer: Three read-only examples are the device's hardware model (`model`), its running OS version (`os_version`), and the timestamp (`time`) on each audit log entry. The API reports all three.
	
4. Week 7's API answered a bad VLAN with a _422_. If the API validated against your model, what would that answer tell the client that it can't now?	
	- Answer: The current `422` response gives a text message saying the VLAN ID must be from 1 to 4094. With the YANG model, it could also give a structured error with the exact field path and the rule that failed. For VLAN `4095`, that would point to `/wic2005-intent:intent/vlans/id` and give the intent model's allowed range of `2..4094`.
	
5. Which change in G4 would break your `sync.py`, or someone else's client — and why didn't yours?
	- Answer: Making `log` mandatory in the scratch copy would block my `sync.py` and older clients whose ACL entries omit that field. The submitted revision keeps `log` optional. My existing `intent.yaml` still passes validation.
	
6. Your network later gains a **measured** value for each entry, such as the round-trip time to a server. Is it configuration or state? How is that marked in YANG, and which NMDA datastore would you read it from?
	- Answer: Measured round-trip time is state. I would mark the leaf `config false;` in YANG and read it from the NMDA `<operational>` datastore, where the device reports the measurement.
---
# AI Declaration

Tool: Chat GPT

Functions: Help me to do the code. Check my answer and my code. And give me the reason for the code.

AI Chat Link: https://chatgpt.com/s/cx_6b09597ef4c88191950994540cdb6157