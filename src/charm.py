#!/usr/bin/env python3
# Copyright 2022 pjds
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following post for a quick-start guide that will help you
develop a new k8s charm using the Operator Framework:

    https://discourse.charmhub.io/t/4208
"""

import logging
from nturl2path import pathname2url
import subprocess
import os
import pathlib
import yaml
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus

logger = logging.getLogger(__name__)


class HeadscaleCharm(CharmBase):
    """Charm the service."""

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.fortune_action, self._on_fortune_action)
        self.framework.observe(self.on.install, self._on_install)

    def cli(self, command):
        components = command.split(" ")
        try:
            output = subprocess.call(components)
        except subprocess.CalledProcessError as ex:
            logging.debug(f"Command failed: {ex}")

    def _on_install(self, event):
        headscale_version = "https://github.com/juanfont/headscale/releases/download/v0.16.4/headscale_0.16.4_linux_amd64"
        self.cli(f"wget --output-document=/usr/local/bin/headscale {headscale_version}")
        commands = [
            "chmod +x /usr/local/bin/headscale",
            "mkdir -p /etc/headscale",
            "mkdir -p /var/lib/headscale",
            "sudo useradd --create-home --home-dir /var/lib/headscale/ --system --user-group --shell /usr/bin/nologin headscale",
            "touch /var/lib/headscale/db.sqlite",
            "chown headscale:headscale -R /var/lib"
        ]
        for command in commands:
            self.cli(command)

    def write_config(self):
        etc_config_path = pathlib.Path("/etc/headscale/config.yaml")

        if not etc_config_path.exists():
            self.cli("touch /etc/headscale/config.yaml")

        etc_config_dict = {
            "server_url": f"https://{self.config['https-server-url']}:{self.config['https-bind-port']}",
            "listen_addr": f"{self.config['https-bind-address']}:{self.config['https-bind-port']}",
            "metrics_listen_addr": "127.0.0.1:9090",
            "grpc_listen_addr": f"{self.config['grpc-bind-address']}:{self.config['grpc-bind-port']}",
            "grpc_allow_insecure": False,
            "private_key_path": "/var/lib/headscale/private.key",
            "noise": {
                "private_key_path": "/var/lib/headscale/noise_private.key"
            },
            "ip_prefixes": [
                "fd7a:115c:a1e0::/48",
                "100.64.0.0/10"
            ],
            "derp": {
                "server": {
                "enabled": False,
                "region_id": 999,
                "region_code": "headscale",
                "region_name": "Headscale Embedded DERP",
                "stun_listen_addr": f"{self.config['stun-bind-address']}:{self.config['stun-bind-port']}"
                },
                "urls": [
                "https://controlplane.tailscale.com/derpmap/default"
                ],
                "paths": [],
                "auto_update_enabled": True,
                "update_frequency": "24h"
            },
            "disable_check_updates": False,
            "ephemeral_node_inactivity_timeout": "30m",
            "node_update_check_interval": "10s",
            "db_type": "sqlite3",
            "db_path": "/var/lib/headscale/db.sqlite",
            "acme_url": "https://acme-v02.api.letsencrypt.org/directory",
            "acme_email": self.config['letsencrypt-acme-email'],
            "tls_letsencrypt_hostname": self.config['letsencrypt-acme-hostname'],
            "tls_client_auth_mode": "relaxed",
            "tls_letsencrypt_cache_dir": "/var/lib/headscale/cache",
            "tls_letsencrypt_challenge_type": "HTTP-01",
            "tls_letsencrypt_listen": ":http",
            "tls_cert_path": "",
            "tls_key_path": "",
            "log_level": "info",
            "acl_policy_path": "",
            "dns_config": {
                "nameservers": [
                "1.1.1.1"
                ],
                "domains": [],
                "magic_dns": True,
                "base_domain": "example.com"
            },
            "unix_socket": "/var/run/headscale/headscale.sock",
            "unix_socket_permission": "0770",
            "logtail": {
                "enabled": False
            },
            "randomize_client_port": False
        }

        systemd_config_location = "/etc/systemd/system/headscale.service"

        systemd_config = """
[Unit]
Description=headscale controller
After=syslog.target
After=network.target

[Service]
Type=simple
User=headscale
Group=headscale
ExecStart=/usr/local/bin/headscale serve
Restart=always
RestartSec=5

# Optional security enhancements
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/lib/headscale /var/run/headscale
AmbientCapabilities=CAP_NET_BIND_SERVICE
RuntimeDirectory=headscale

[Install]
WantedBy=multi-user.target
"""
        configs = {
            etc_config_path: etc_config_dict, 
            systemd_config_location: systemd_config
        }

        for config, contents in configs.items():
            with open(config, 'w') as fh:
                fh.write(yaml.dump(contents))
        systemd_commands = [
                "usermod -a -G headscale current_user",
                "systemctl daemon-reload",
                "systemctl enable --now headscale",
                "systemctl restart headscale"
            ]

        for command in systemd_commands:
            self.cli(command)


        self.unit.status = ActiveStatus()


        


    def _on_config_changed(self, _):
        """Just an example to show how to deal with changed configuration.

        TEMPLATE-TODO: change this example to suit your needs.
        If you don't need to handle config, you can remove this method,
        the hook created in __init__.py for it, the corresponding test,
        and the config.py file.

        Learn more about config at https://juju.is/docs/sdk/config
        """
        self.write_config()

    def _on_fortune_action(self, event):
        """Just an example to show how to receive actions.

        TEMPLATE-TODO: change this example to suit your needs.
        If you don't need to handle actions, you can remove this method,
        the hook created in __init__.py for it, the corresponding test,
        and the actions.py file.

        Learn more about actions at https://juju.is/docs/sdk/actions
        """
        fail = event.params["fail"]
        if fail:
            event.fail(fail)
        else:
            event.set_results({"fortune": "A bug in the code is worth two in the documentation."})


if __name__ == "__main__":
    main(HeadscaleCharm)
