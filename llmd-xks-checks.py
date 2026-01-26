#!/usr/bin/env python3
"""
LLMD xKS preflight checks.
"""

import configargparse
import sys
import logging
import os
import kubernetes

class LLMDXKSChecks:
    def __init__(self, **kwargs):
        self.log_level = kwargs.get("log_level", "INFO")
        self.logger = self._log_init()

        self.cloud_provider = kwargs.get("cloud_provider", "auto")

        self.logger.debug(f"Log level: {self.log_level}")
        self.logger.debug(f"Arguments: {kwargs}")
        self.logger.info("LLMDXKSChecks initialized")

        self.k8s_api = self._k8s_connection()

        if self.k8s_api is None:
            self.logger.error("Failed to connect to Kubernetes cluster")
            sys.exit(1)

        if self.cloud_provider == "auto":
            self.cloud_provider = self.detect_cloud_provider()
            if self.cloud_provider == "none":
                self.logger.error("Failed to detect cloud provider")
                sys.exit(2)
            self.logger.info(f"Cloud provider detected: {self.cloud_provider}")
        else:
            self.logger.info(f"Cloud provider specified: {self.cloud_provider}")

        self.tests = [
            ]

        self.run(self.tests)

    def _log_init(self):
        logger = logging.getLogger(__name__)
        logger.setLevel(self.log_level)
        logger.addHandler(logging.StreamHandler())
        return logger

    def _k8s_connection(self):
        try:
            kubernetes.config.load_kube_config()
            api = kubernetes.client.CoreV1Api()
        except Exception as e:
            self.logger.error(f"{e}")
            return None
        self.logger.info("Kubernetes connection established")
        return api

    def detect_cloud_provider(self):
        clouds = {
            "none": 0,
            "azure": 0,
            "aws": 0
        }
        nodes = self.k8s_api.list_node()
        for node in nodes.items:
            labels = node.metadata.labels
            if "kubernetes.azure.com/cluster" in labels:
                clouds["azure"] += 1

        return max(clouds, key=clouds.get)

    def run(self, tests=[]):
        for test in tests:
            test()
        return True

def cli_arguments():
    default_config_paths = [
        os.path.expanduser("~/.llmd-xks-preflight.conf"),
        os.path.join(os.getcwd(), "llmd-xks-preflight.conf"),
        "/etc/llmd-xks-preflight.conf",
    ]
    
    parser = configargparse.ArgumentParser(
        description="LLMD xKS preflight checks.",
        default_config_files=default_config_paths,
        config_file_parser_class=configargparse.ConfigparserConfigFileParser,
        auto_env_var_prefix="LLMD_XKS_",
    )
    
    parser.add_argument(
        "-c", "--config",
        is_config_file=True,
        help="Path to config file"
    )
    
    parser.add_argument(
        "-l", "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        env_var="LLMD_XKS_LOG_LEVEL",
        help="Set the log level (default: INFO)"
    )
    
    parser.add_argument(
        "-k", "--kube-config",
        type=str,
        default=None,
        env_var="KUBECONFIG",
        help="Path to the kubeconfig file"
    )

    parser.add_argument(
        "-u", "--cloud-provider",
        choices=["auto", "azure"],
        default="auto",
        env_var="LLMD_XKS_CLOUD_PROVIDER",
        help="Cloud provider to perform checks on (by default, try to auto-detect)"
    )
    
    return parser.parse_args()

def main():
    args = cli_arguments()
    llmd_xks_checks = LLMDXKSChecks(**vars(args))

if __name__ == "__main__":
    sys.exit(main())