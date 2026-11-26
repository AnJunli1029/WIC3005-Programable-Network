# Lab

1. What does `docker network inspect apilab` show, and how is it built from Week 6's building blocks?

   `apilab` is a local Docker bridge network. Its subnet is `172.18.0.0/16` and its gateway is `172.18.0.1`. The `api` container has IP `172.18.0.2`, and `client` has IP `172.18.0.3`.

   Each container has its own network namespace. A virtual Ethernet pair (`veth`) connects each namespace to the Linux bridge. Docker DNS lets `client` reach the API using the name `api`.

2. For each status code in Step 2, what should a client do next — and which of them should it never retry?

   | Code | What should the client do? |
   |---|---|
   | `200 OK` | Use the response. The request succeeded. |
   | `400 Bad Request` | Fix the request, such as invalid JSON. |
   | `401 Unauthorized` | Log in again and retry with a fresh token. |
   | `403 Forbidden` | Use an account with the right permission. |
   | `404 Not Found` | Check the URL or resource ID. |
   | `405 Method Not Allowed` | Check the `Allow` header and use a supported method. |
   | `409 Conflict` | Check the current data. For example, use `PUT` if the VLAN already exists and you want to update it. |
   | `422 Unprocessable Entity` | Fix the invalid value, such as a VLAN ID outside the allowed range. |
   | `429 Too Many Requests` | Wait for the time in `Retry-After`, then retry. |

   Never automatically retry the same request after `400`, `403`, `404`, `405`, `409`, or `422`. Fix the cause first.

3. Why did `retry_naive.py` create duplicates, and how exactly does your fix prevent them? Why must the `Idempotency-Key` be chosen once, before the first attempt?

   `retry_naive.py` created duplicates because the API saved the ACL entry before dropping the response. The script got no reply, so it sent the same `POST` again and created another entry.

   `retry_safe.py` creates one `Idempotency-Key` before the first attempt and uses it for every retry of the same request. The API recognizes the key and returns the first result. If the script creates a new key for each retry, the API treats each retry as a new request.

4. How many requests did `inventory.py` send to read your devices, and why more than the number of pages?

   The script read **216 devices across 22 pages**. In Step 5, it sent **32 requests** in total. That included 22 successful page requests, 1 login request, 1 request that got `429`, and 8 that got `503`.

   In Step 6, it sent **37 requests**. That included 22 successful page requests, 3 logins, 10 requests that got `429`, and 2 that got `401` when the token expired.

5. What did you find in the OpenAPI document that you'd never have guessed?

   I learned that the devices endpoint has a `site` parameter. I used `site=kl-hq` to list only that site's devices. The largest page size was `50`, so I followed the `next` link to get all **54 devices** in two pages.

---

# Assignment

1. How does `sync.py` decide what to change? Walk through one VLAN that was created, one that was renamed or deleted, and one ACL entry.

   `sync.py` reads the current VLANs and ACL entries from the API and compares them with `intent.yaml`. It compares VLANs by ID and ACLs by their rule fields. The API's ACL IDs are only used when deleting entries. In my run, VLAN 30 was missing, so the script created it as `guests`. VLAN 99 was absent from the intent, so the script deleted it. The `guests-no-ssh` rule was missing, so the script added a rule denying TCP port 22 from `10.16.30.0/24` to `10.16.20.0/24`. The script leaves the API's reserved VLAN 1 in place.

2. For each kind of request your script sends, why is it safe to retry — or why doesn't your script retry it?

   - `GET` reads the state, so repeating it leaves the configuration untouched.
   - VLAN `PUT` sets the same name for the same VLAN ID each time.
   - `DELETE` removes a VLAN or ACL by ID. If a retry receives `404`, that resource is already gone.
   - ACL `POST` uses the same `Idempotency-Key` and body on each retry, so the API can return the first result.
   - The login `POST` obtains a token. The script sends each login call once. When a configuration request gets `401`, it logs in again and retries that request with the fresh token.

   For `429`, the script waits for `Retry-After`. For `503`, a lost connection, or a timeout, it increases the delay between attempts and stops after six temporary failures. Other HTTP errors stop the operation.

3. VLANs have PUT; ACL entries only have POST. How did that change your design, and how do you choose each `Idempotency-Key`? What would go wrong with a new key for every attempt — or the same key for every run?

   A VLAN has a known ID, so `PUT` can create it or set its name at the same URL. ACL IDs are assigned by the API, so I keep matching rules, use `POST` for missing rules, and delete extra rules by ID.

   For each new ACL, the script generates one UUID before sending the first `POST`. It saves that key for all attempts at that creation. A new key on every retry could create duplicates if the first request succeeded and its reply was lost. Reusing an old key in a later run could replay an old result even after its rule was deleted, or return `422` if the body changed.

4. What happens if two people run `sync.py` with different intents at the same moment? What would the API need to make that safe?

   Both clients can read the same starting state and then apply different plans. Their changes can overlap, so one client can overwrite or delete what the other just changed. The final configuration can be a mix of both intents. The API could provide a configuration version and apply a whole plan in one transaction only if that version is still current. A client with an old version would read the state again and make a new plan.

5. Where are your credentials, and how did you make sure no token or password is in your repository?

   I set `LAB_USERNAME` and `LAB_PASSWORD` as environment variables in the client shell. `sync.py` obtains a bearer token from the API and keeps it in memory. I checked the client scripts and saved evidence for password and token values and replaced the example password in `inventory.py` with a placeholder. Before committing, I will review the staged files with `git diff --cached` and keep the course-provided server file with its demo accounts out of the commit.

## AI use

I used OpenAI Codex to translate parts of the lab instructions, interpret terminal output, help write `retry_safe.py`, implement and test `inventory.py` and `sync.py`, add two ACL rules to `intent.yaml`, check the evidence, and draft the README answers. I ran the Docker commands and collected the evidence from my own lab runs.