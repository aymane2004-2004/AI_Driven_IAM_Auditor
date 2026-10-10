import sys; sys.path.insert(0, "src")
from seed_tenant import SCENARIOS, apply_overlay
from collect_entra import build_inventory
from rules import run_rules

def test_every_scenario_triggers_exactly_its_expected_rules():
    users, entra, azure, sps, leavers, state = [], [], [], {}, set(), {"users": {}}
    for s in SCENARIOS:
        k = s["key"]; state["users"][k] = k
        if s["type"] == "service":
            sps[k] = {"displayName": s["name"]}
        else:
            users.append({"id": k, "displayName": s["name"], "userPrincipalName": f"{s['upn']}@t.onmicrosoft.com",
                          "jobTitle": s["title"] or None, "department": s["dept"] or None, "accountEnabled": s["enabled"],
                          "userType": "Guest" if s["type"] == "guest" else "Member"})
        entra += [(k, r) for r in s["roles"]]
        azure += [(k, r) for r in s["azure"]]
        if s["leaver"]: leavers.add(f"{s['upn']}@t.onmicrosoft.com")
    inv = apply_overlay(build_inventory(users, {}, entra, azure, sps, leavers), state)
    found = {}
    for f in run_rules(inv): found.setdefault(f["user_id"], set()).add(f["rule"])
    for s in SCENARIOS:
        assert found.get(s["key"], set()) == s["expected"], (s["key"], found.get(s["key"]))
