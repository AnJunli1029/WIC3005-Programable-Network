# WIC3005 — Programable Network

Week 2 Lab: https://anjunli1029.github.io/WIC3005-Programable-Network/

Week 3 Lab: https://anjunli1029.github.io/WIC3005-Programable-Network/week3/

Week 4 Lab:

1. Why did the first firewall rule in Step 3 have no effect, and why does blocking h1 → h3 also break h3 → h1?
- The first firewall rule had no effect because the drop rule and the existing forwarding rule had the same default priority (32768). Both rules matched the packets with the same priority, and OpenFlow does not guarantee which rule wins. In my experiment, the forwarding rule was used, so the drop rule had no effect. After increasing the drop rule's priority to 40000, the firewall successfully blocked traffic from h1 to h3.

- Blocking h1 → h3 also affected h3 → h1 because ICMP ping requires an echo request and an echo reply. When h3 sends a ping to h1, h1 must send a reply back to h3. However, the firewall blocks packets from 10.16.0.1 to 10.16.0.3, including the echo reply. Therefore, h3 cannot successfully ping h1.

2. In Step 5, why did one conversation survive the controller failure and another didn't?

- The h1 → h2 conversation continued working because the controller had already installed forwarding rules in the switch's flow table. These existing rules allowed the switch to forward packets without contacting the controller.

- However, h1 → h3 was a new conversation, so the switch needed the controller to install new forwarding rules. Since the controller was disconnected, the new conversation failed.

- The existing rules also had an idle_timeout of 60 seconds. If they were not used for 60 seconds, they would expire, and h1 → h2 would also fail because the controller was unavailable.

3. Secure or standalone: which would you choose for a campus network, and what does the other one cost you?

- I would choose secure mode for a campus network because security is important for protecting students, staff, and university data. In secure mode, the switch keeps its existing flow rules when the controller fails, including any firewall rules that are still installed. This helps maintain security policies.

- The disadvantage is that new conversations requiring the controller may fail, reducing network availability.

- Standalone mode provides better availability because the switch falls back to normal learning-switch behavior when the controller is disconnected. However, this can bypass controller-installed firewall rules and security policies, which creates security risks.

- Therefore, I would prefer secure mode to maintain network security, even though it may temporarily affect connectivity.
