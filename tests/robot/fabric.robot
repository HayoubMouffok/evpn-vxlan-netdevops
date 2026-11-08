*** Settings ***
Documentation     Validation de la fabric EVPN-VXLAN générée depuis NetBox.
...               Chaque test réessaie pendant la convergence du réseau.
Library           FabricLibrary.py

*** Variables ***
@{SWITCHES}       spine1    spine2    leaf1    leaf2
@{LEAFS}          leaf1    leaf2

*** Test Cases ***
Sessions BGP underlay établies sur toute la fabric
    FOR    ${node}    IN    @{SWITCHES}
        Wait Until Keyword Succeeds    3 min    5 s    BGP Peers Should Be Established    ${node}    ipv4Unicast
    END

Sessions BGP EVPN établies sur toute la fabric
    FOR    ${node}    IN    @{SWITCHES}
        Wait Until Keyword Succeeds    3 min    5 s    BGP Peers Should Be Established    ${node}    l2VpnEvpn
    END

VNI 100 connu des deux leafs avec un VTEP distant
    FOR    ${node}    IN    @{LEAFS}
        Wait Until Keyword Succeeds    3 min    5 s    VNI Should Have Remote VTEP    ${node}    100
    END

Redondance : leaf1 joint leaf2 par les deux spines (ECMP)
    Wait Until Keyword Succeeds    1 min    5 s    Route Should Have Nexthops    leaf1    10.0.0.12/32    2

Les serveurs communiquent en L2 à travers le tunnel VXLAN
    Wait Until Keyword Succeeds    1 min    5 s    Host Should Ping    host1    10.10.100.12
