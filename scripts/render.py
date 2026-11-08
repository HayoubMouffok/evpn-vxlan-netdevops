"""Génère la topologie containerlab et les configurations FRR à partir de NetBox (source de vérité)."""
import os
from pathlib import Path

import pynetbox
import yaml
from jinja2 import Environment, FileSystemLoader

URL = os.getenv("NETBOX_URL", "http://localhost:8000")
TOKEN = os.getenv("NETBOX_TOKEN", "0123456789abcdef0123456789abcdef01234567")
ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
FRR_IMAGE = "quay.io/frrouting/frr:9.1.0"


def main():
    nb = pynetbox.api(URL, token=TOKEN)
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), trim_blocks=True, lstrip_blocks=True)

    devices = {d.name: d for d in nb.dcim.devices.all()}
    ips = {}  # interface id -> adresse
    for ip in nb.ipam.ip_addresses.all():
        if ip.assigned_object_id:
            ips[ip.assigned_object_id] = ip.address

    nodes, links, seen = {}, [], set()
    for name, dev in sorted(devices.items()):
        role = dev.role.slug
        ctx = dev.local_context_data or {}
        interfaces = list(nb.dcim.interfaces.filter(device_id=dev.id))
        loopback = next((ips[i.id] for i in interfaces if i.name == "lo" and i.id in ips), None)

        fabric_ifaces, neighbors = [], []
        for i in interfaces:
            if i.name == "lo" or not i.link_peers:
                continue
            peer = i.link_peers[0]
            peer_dev = devices[peer["device"]["name"] if isinstance(peer, dict) else peer.device.name]
            peer_id = peer["id"] if isinstance(peer, dict) else peer.id
            key = tuple(sorted([(name, i.name), (peer_dev.name, peer["name"] if isinstance(peer, dict) else peer.name)]))
            if key not in seen:
                seen.add(key)
                links.append({"endpoints": [f"{a}:{b}" for a, b in key]})
            if i.id in ips and peer_id in ips and role in ("spine", "leaf"):
                fabric_ifaces.append({"name": i.name, "ip": ips[i.id]})
                neighbors.append({"ip": ips[peer_id].split("/")[0],
                                  "asn": (peer_dev.local_context_data or {})["asn"],
                                  "peer": peer_dev.name})

        out = BUILD / name
        out.mkdir(parents=True, exist_ok=True)
        if role in ("spine", "leaf"):
            (out / "frr.conf").write_text(env.get_template("frr.conf.j2").render(
                hostname=name, role=role, asn=ctx["asn"], loopback=loopback,
                router_id=loopback.split("/")[0], interfaces=fabric_ifaces, neighbors=neighbors))
            node = {"image": FRR_IMAGE, "binds": [
                f"{name}/frr.conf:/etc/frr/frr.conf",
                "../configs/common/daemons:/etc/frr/daemons",
                "../configs/common/vtysh.conf:/etc/frr/vtysh.conf"]}
            if role == "leaf":
                (out / "vxlan.sh").write_text(env.get_template("vxlan.sh.j2").render(
                    vtep=loopback.split("/")[0], vnis=ctx.get("vnis", [])))
                node["binds"].append(f"{name}/vxlan.sh:/vxlan.sh")
                node["exec"] = ["sh /vxlan.sh"]
            nodes[name] = node
        else:
            host_ip = next(ips[i.id] for i in interfaces if i.id in ips)
            nodes[name] = {"image": "alpine:3.20", "exec": [f"ip addr add {host_ip} dev eth1"]}

    topo = {"name": "evpn", "topology": {"defaults": {"kind": "linux"}, "nodes": nodes, "links": links}}
    (BUILD / "fabric.clab.yml").write_text(yaml.safe_dump(topo, sort_keys=False))
    print(f"Généré : {len(nodes)} nœuds, {len(links)} liens -> {BUILD}")


if __name__ == "__main__":
    main()
