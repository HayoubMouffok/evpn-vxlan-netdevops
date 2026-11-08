"""Charge l'intention de la fabric dans NetBox (sites, équipements, interfaces, IP, câbles)."""
import os
import sys
import time

import pynetbox
import requests
import yaml

URL = os.getenv("NETBOX_URL", "http://localhost:8000")
TOKEN = os.getenv("NETBOX_TOKEN", "0123456789abcdef0123456789abcdef01234567")


def wait_for_netbox(timeout=600):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{URL}/api/status/", headers={"Authorization": f"Token {TOKEN}"}, timeout=5)
            if r.ok:
                print("NetBox prêt :", r.json().get("netbox-version"))
                return
        except requests.RequestException:
            pass
        time.sleep(5)
    sys.exit("NetBox injoignable")


def get_or_create(endpoint, lookup, **extra):
    obj = endpoint.get(**lookup)
    return obj or endpoint.create(**lookup, **extra)


def main():
    wait_for_netbox()
    nb = pynetbox.api(URL, token=TOKEN)
    intent = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), "fabric_intent.yml")))

    site = get_or_create(nb.dcim.sites, {"slug": intent["site"]}, name=intent["site"].upper())
    vendor = get_or_create(nb.dcim.manufacturers, {"slug": "frrouting"}, name="FRRouting")
    dtype = get_or_create(nb.dcim.device_types, {"slug": "frr-container"}, model="FRR container", manufacturer=vendor.id)
    roles = {r: get_or_create(nb.dcim.device_roles, {"slug": r}, name=r.capitalize(), color="2196f3")
             for r in ("spine", "leaf", "server")}

    devices, ifaces = {}, {}
    for name, d in intent["devices"].items():
        ctx = {k: d[k] for k in ("asn", "vnis") if k in d}
        devices[name] = get_or_create(nb.dcim.devices, {"name": name}, site=site.id,
                                      device_type=dtype.id, role=roles[d["role"]].id,
                                      local_context_data=ctx or None)
        if "loopback" in d:
            lo = get_or_create(nb.dcim.interfaces, {"device_id": devices[name].id, "name": "lo"}, type="virtual")
            get_or_create(nb.ipam.ip_addresses, {"address": d["loopback"]}, role="loopback",
                          assigned_object_type="dcim.interface", assigned_object_id=lo.id)

    def iface(dev, name):
        key = (dev, name)
        if key not in ifaces:
            ifaces[key] = get_or_create(nb.dcim.interfaces, {"device_id": devices[dev].id, "name": name}, type="1000base-t")
        return ifaces[key]

    for a_dev, a_if, a_ip, b_dev, b_if, b_ip in intent["links"]:
        a, b = iface(a_dev, a_if), iface(b_dev, b_if)
        for i, ip in ((a, a_ip), (b, b_ip)):
            if ip:
                get_or_create(nb.ipam.ip_addresses, {"address": ip},
                              assigned_object_type="dcim.interface", assigned_object_id=i.id)
        if not a.cable:
            nb.dcim.cables.create(a_terminations=[{"object_type": "dcim.interface", "object_id": a.id}],
                                  b_terminations=[{"object_type": "dcim.interface", "object_id": b.id}],
                                  status="connected")

    for name, d in intent["devices"].items():
        if "ip" in d:
            get_or_create(nb.ipam.ip_addresses, {"address": d["ip"]},
                          assigned_object_type="dcim.interface", assigned_object_id=iface(name, "eth1").id)
    print(f"{len(devices)} équipements, {len(intent['links'])} câbles chargés dans NetBox")


if __name__ == "__main__":
    main()
