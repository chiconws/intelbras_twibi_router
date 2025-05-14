net_link_status = {"net_link_status": [{"net_status": "3", "id": "1"}]}

lan_info = {
    "lan_info": {
        "lan_ip": "192.168.5.1",
        "lan_mask": "255.255.255.0",
        "dhcp_en": "1",
        "start_ip": "192.168.5.5",
        "end_ip": "192.168.5.200",
        "lease_time": "86400",
        "dns1": "192.168.5.1",
        "dns2": "",
    }
}

link_module = {"link_module": [{"id": "1", "link_mode": "2"}]}

localhost = {}

getversion = {
    "getversion": {
        "hasNew": "0",
        "version": "",
        "changelog": "",
        "current_version": "1.1.10",
        "sysHasNew": "1",
    }
}

getupgradestatus = {"getupgradestatus": {"code": "1"}}

guest_info = {
    "guest_info": {
        "guest_en": "0",
        "guest_ssid": "Visitante",
        "guest_pass": "12345678",
        "guest_time": "8",
        "limit": "0",
    }
}

port_list = {"port_list": {"list": []}}

serach_node = {"serach_node": []}

static_ip = {
    "static_ip": [
        {
            "is_bind": "0",
            "status": "0",
            "dev_name": "",
            "dev_mac": "F6:3A:80:09:BA:4B",
            "dev_ip": "192.168.5.75",
        },
        {
            "is_bind": "0",
            "status": "1",
            "dev_name": "",
            "dev_mac": "00:12:33:37:94:DE",
            "dev_ip": "192.168.5.48",
        },
        {
            "is_bind": "1",
            "status": "1",
            "dev_name": "",
            "dev_mac": "48:DA:35:6F:C3:65",
            "dev_ip": "192.168.5.187",
        },
        {
            "is_bind": "1",
            "status": "1",
            "dev_name": "",
            "dev_mac": "00:12:33:A7:90:AF",
            "dev_ip": "192.168.5.124",
        },
    ]
}

static_wan_info = {
    "static_wan_info": [
        {
            "id": "1",
            "ip": "",
            "netmask": "",
            "gw": "",
            "mac": "D8:77:8B:99:AC:69",
            "first_dns": "",
            "sec_dns": "",
        }
    ]
}

dynamic_wan_info = {"dynamic_wan_info": [{"id": "1"}]}

mac_clone = {
    "mac_clone": [
        {
            "id": "1",
            "clone_type": "0",
            "clone_mac": "D8:77:8B:99:AC:69",
            "default_mac": "D8:77:8B:99:AC:62",
            "dut_mac": "48:DA:35:6F:C3:65",
        }
    ]
}

dns_conf = {
    "dns_conf": {
        "first_dns": "",
        "sec_dns": "",
        "mode": "0",
        "first_dns_v6": "",
        "sec_dns_v6": "",
    }
}

elink = {}

upnp_info = {"upnp_info": {"upnp_en": "1"}}

tr069_info = {
    "tr069_info": {
        "tr069_en": "0",
        "acs_addr": "",
        "acs_user": "",
        "acs_pass": "",
        "notice_en": "0",
        "notice_time": "43200",
        "con_req_en": "0",
        "terminal_user": "",
        "terminal_pass": "",
        "port": "",
        "stun_en": "0",
        "stun_addr": "",
        "stun_port": "3478",
    }
}

remote_web = {
    "remote_web": {"remote_en": "0", "remote_ip": "0.0.0.0", "remote_port": "8080"}
}

net_link_check = {"net_link_check": [{"id": "1", "link_mode": "2"}]}

node_info = {
    "node_info": [
        {
            "id": "0",
            "ip": "192.168.5.110",
            "role": "0",
            "netmask": "",
            "gw": "",
            "first_dns": "",
            "sec_dns": "",
            "up_speed": "",
            "down_speed": "",
            "serial_number": "SWSI100347178",
            "led": "1",
            "location": "",
            "lan_mac": "24:FD:0D:9A:82:2F",
            "wan_mac": "24:FD:0D:9A:82:36",
            "5Gwifi_mac": "24:FD:0D:9A:82:33",
            "2Gwifi_mac": "24:FD:0D:9A:82:30",
            "dut_name": "Twibi Fast",
            "dut_version": "1.1.10",
            "sn": "SWSI100347178",
            "groupsn": "SWSI29157827Q,SWSI100347178",
            "Uptime": "17662",
            "up_date": "30-03-2025 08:34:42",
            "ipv6": "fe80::da77:8bff:fe99:ac62/64",
            "net_status": "1",
            "link_status": "1",
            "link_quality": "-82",
        },
        {
            "id": "1",
            "ip": "192.168.5.1",
            "role": "1",
            "netmask": "",
            "gw": "",
            "first_dns": "",
            "sec_dns": "",
            "up_speed": "",
            "down_speed": "",
            "serial_number": "SWSI29157827Q",
            "led": "1",
            "location": "",
            "lan_mac": "D8:77:8B:99:AC:62",
            "wan_mac": "D8:77:8B:99:AC:69",
            "5Gwifi_mac": "D8:77:8B:99:AC:66",
            "2Gwifi_mac": "D8:77:8B:99:AC:63",
            "dut_name": "Twibi Fast",
            "dut_version": "1.1.10",
            "sn": "SWSI29157827Q",
            "groupsn": "SWSI29157827Q,SWSI100347178",
            "Uptime": "17658",
            "up_date": "30-03-2025 08:34:42",
            "ipv6": "fe80::da77:8bff:fe99:ac62/64",
            "net_status": "1",
            "link_status": "1",
        },
    ]
}

wan_info = {
    "wan_info": [
        {
            "id": "1",
            "ip": "100.64.23.132",
            "netmask": "255.255.255.255",
            "gw": "10.254.254.19",
            "mac": "D8:77:8B:99:AC:69",
            "first_dns": "177.71.32.73",
            "sec_dns": "177.71.32.74",
            "ipv6": "fe80::3059:f163:a2aa:4136/10",
            "ipv6_gw": "",
            "ipv6_first_dns": "",
            "ipv6_sec_dns": "",
        }
    ]
}

wan_statistic = {
    "wan_statistic": [
        {
            "id": "1",
            "up_speed": "0",
            "down_speed": "0",
            "ttotal_up": "0",
            "ttotal_down": "0",
        }
    ]
}

wifi = {
    "wifi": {
        "ssid": "Rodrigo",
        "type": "aes",
        "security": "psk psk2",
        "pass": "rodrigo01",
    }
}
