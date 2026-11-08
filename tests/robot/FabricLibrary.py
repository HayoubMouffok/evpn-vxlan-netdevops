"""Bibliothèque Robot Framework : mots-clés de vérification de la fabric EVPN-VXLAN."""
import json
import subprocess

LAB = "evpn"


class FabricLibrary:
    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    def _exec(self, node, *cmd):
        return subprocess.run(["docker", "exec", f"clab-{LAB}-{node}", *cmd],
                              capture_output=True, text=True, check=False)

    def _vtysh_json(self, node, command):
        return json.loads(self._exec(node, "vtysh", "-c", f"{command} json").stdout or "{}")

    def bgp_peers_should_be_established(self, node, afi="ipv4Unicast"):
        """Échoue si une session BGP de `node` pour la famille `afi` n'est pas Established."""
        peers = self._vtysh_json(node, "show bgp summary").get(afi, {}).get("peers", {})
        if not peers:
            raise AssertionError(f"{node} : aucun voisin BGP {afi}")
        down = [ip for ip, p in peers.items() if p.get("state") != "Established"]
        if down:
            raise AssertionError(f"{node} : sessions {afi} non établies vers {down}")

    def vni_should_have_remote_vtep(self, node, vni):
        """Échoue si le VNI n'existe pas sur `node` ou n'a aucun VTEP distant."""
        data = self._vtysh_json(node, f"show evpn vni {vni}")
        if data.get("vni") != int(vni) or not data.get("remoteVteps"):
            raise AssertionError(f"{node} : VNI {vni} absent ou sans VTEP distant")

    def route_should_have_nexthops(self, node, prefix, count):
        """Échoue si `prefix` n'a pas exactement `count` next-hops (ECMP)."""
        routes = self._vtysh_json(node, f"show ip route {prefix}").get(prefix, [])
        found = len(routes[0].get("nexthops", [])) if routes else 0
        if found != int(count):
            raise AssertionError(f"{node} : {found} next-hop(s) vers {prefix}, {count} attendus")

    def host_should_ping(self, src, dst):
        """Échoue si `src` ne joint pas `dst` en ping."""
        if self._exec(src, "ping", "-c", "2", "-W", "2", dst).returncode != 0:
            raise AssertionError(f"{src} ne joint pas {dst}")
