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
            {
                "name": "instance_type",
                "function": self.test_instance_type,
                "description": "Test if the cluster has at least one supported instance type",
                "suggested_action": "Provision a cluster with at least one supported instance type",
                "result": False
            },
            {
                "name": "gpu_availablity",
                "function": self.test_gpu_availablity,
                "description": "Test if the cluster has GPU drivers",
                "suggested_action": "Provision a cluster with at least one supported GPU driver",
                "result": False
            },
        ]

        self.run(self.tests)
        self.report()

    def _log_init(self):
        logger = logging.getLogger(__name__)
        logger.setLevel(self.log_level)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)
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

    def test_gpu_availablity(self):
        def nvidia_driver_present(node):
            if "nvidia.com/gpu" in node.status.allocatable.keys():
                if int(node.status.allocatable["nvidia.com/gpu"] ) > 0:
                    return True
                else:
                    self.logger.warning(f"No allocatabled NVIDIA GPUs on node {node.metadata.name} - no NVIDIA GPU drivers present")
                    return False
            else:
                self.logger.warning(f"No NVIDIA GPU drivers present on node {node.metadata.name} - no NVIDIA GPU accelerators present")
                return False
        
        accelerators = {
            "nvidia": 0,
            "other": 0,
        }
        nodes = self.k8s_api.list_node()
        for node in nodes.items:
            labels = node.metadata.labels
            if "nvidia.com/gpu.present" in labels:
                accelerators["nvidia"] += 1
                self.logger.info(f"NVIDIA GPU accelerator present on node {node.metadata.name}")
                if not nvidia_driver_present(node):
                    return False
            else:
                accelerators["other"] += 1
        if accelerators["other"] == len(nodes.items):
            self.logger.error("No supported GPU drivers found")
            return False
        else:
            self.logger.info("At least one supported GPU driver found")
            return True
            

    def test_instance_type(self):
        def azure_instance_type(self):
            instance_types = {
                "Standard_NC24ads_A100_v4": 0,
                "Standard_ND96asr_v4": 0,
                "Standard_ND96amsr_A100_v4": 0,
                "Standard_ND96isr_H100_v5": 0,
                "Standard_ND96isr_H200_v5": 0,
            }
            nodes = self.k8s_api.list_node()
            for node in nodes.items:
                labels = node.metadata.labels
                if "beta.kubernetes.io/instance-type" in labels:
                    try:
                        instance_types[labels["beta.kubernetes.io/instance-type"]] += 1
                    except KeyError:
                        # ignore unknown instance types
                        pass
            max_instance_type = max(instance_types, key=instance_types.get)
            if instance_types[max_instance_type] == 0:
                self.logger.error("No supported instance type found")
                return False
            else:
                self.logger.info("At least one supported Azure instance type found")
                self.logger.debug(f"Instances by type: {instance_types}")
                return True

        if self.cloud_provider == "azure":
            return azure_instance_type(self)
        else:
            self.logger.error("Unsupported cloud provider")
            return False

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
            if test["function"]():
                self.logger.debug(f"Test {test['name']} passed")
                test["result"] = True
            else:
                self.logger.error(f"Test {test['name']} failed")
                test["result"] = False
        return None

    def report(self):
        for test in self.tests:
            if test["result"]:
                print(f"Test {test['name']} PASSED")
            else:
                print(f"Test {test['name']} FAILED")
                print(f"    Suggested action: {test['suggested_action']}")
        return None


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
    LLMDXKSChecks(**vars(args))


if __name__ == "__main__":
    sys.exit(main())
