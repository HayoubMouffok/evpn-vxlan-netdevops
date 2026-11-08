"""Tests de la fabric EVPN-VXLAN déployée (pytest)."""
import json
import subprocess
import time

import pytest

LAB = "evpn"
SWITCHES = ["spine1", "spine2", "leaf1", "leaf2"]


def run(node, *cmd):
    return subprocess.run(["docker", "exec", f"clab-{LAB}-{node}", *cmd],
                          capture_output=True, text=True, check=False)


def vtysh_json(node, command):
    return json.loads(run(node, "vtysh", "-c", f"{command} json").stdout or "{}")


def wait_until(check, timeout=180, step=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if check():
            return True
        time.sleep(step)
    return check()


@pytest.mark.parametrize("node", SWITCHES)
@pytest.mark.parametrize("afi", ["ipv4Unicast", "l2VpnEvpn"])
def test_sessions_bgp_etablies(node, afi):
    def established():
        peers = vtysh_json(node, "show bgp summary").get(afi, {}).get("peers", {})
        return peers and all(p.get("state") == "Established" for p in peers.values())
    assert wait_until(established), f"{node} : sessions {afi} non établies"


@pytest.mark.parametrize("node", ["leaf1", "leaf2"])
def test_vni_100_avec_vtep_distant(node):
    def vni_ok():
        vni = vtysh_json(node, "show evpn vni 100")
        return vni.get("vni") == 100 and len(vni.get("remoteVteps", [])) >= 1
    assert wait_until(vni_ok), f"{node} : VNI 100 sans VTEP distant"


def test_loopbacks_en_ecmp():
    routes = vtysh_json("leaf1", "show ip route 10.0.0.12/32").get("10.0.0.12/32", [])
    assert routes and len(routes[0].get("nexthops", [])) == 2, "leaf1 doit joindre leaf2 via les 2 spines"


def test_ping_l2_host1_host2_via_vxlan():
    assert wait_until(lambda: run("host1", "ping", "-c", "2", "-W", "2", "10.10.100.12").returncode == 0, 60)
