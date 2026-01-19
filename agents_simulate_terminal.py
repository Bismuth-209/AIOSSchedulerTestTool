import asyncio
import math
import os.path
import sys
import time
from threading import Thread
from time import sleep
from typing import Any, Dict

import yaml

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multi_agents.agent import TaskItem
from multi_agents.agent_manager import AgentManager


def get_resources_path(old_resources_path: str):
    while old_resources_path == "Not found":
        import_resource_from_other = input(f"Import resource from other path: ")
        if import_resource_from_other:
            if not os.path.exists(import_resource_from_other):
                print(f"Directory not exist.")
            else:
                old_resources_path = os.path.abspath(import_resource_from_other)
    return old_resources_path


def parse_start_cmd(resources_path: str, args: list[str]):
    automatic = False
    async_task_load = False
    change_conf = False
    conf_name = "configs"

    in_error = False

    for arg in args:
        if change_conf:
            if arg.startswith("-"):
                print("[ERROR]Config file name didn't provided.")
                in_error = True
                continue
            conf_name = arg
            change_conf = False
        if arg == "-a":
            automatic = True
        elif arg == "-A":
            async_task_load = True
        elif arg == "-c":
            change_conf = True
        else:
            print("[ERROR]Invalid argument")
            in_error = True
    if in_error:
        return None
    configs = load_configs(os.path.join(resources_path, conf_name + ".yml"))
    configs["automatic"] = automatic or configs.get("automatic", False)
    configs["async_task_load"] = async_task_load or configs.get("async_task_load", False)
    return configs


def load_configs(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config


def run_agents_simulation(resources_path: str, configs: Dict[str, Any]):
    times = {}
    manager = AgentManager(
        os.path.join(resources_path, "agents"),
        os.path.join(resources_path, "outputs"),
        configs
    )
    times["start"] = time.time()
    manager.load_agents(configs.get("agents", None))

    # todo: responsibility of manager
    if not configs.get("automatic", False):
        task_seq = configs.get("task_seq", [])
        manager.load_task_sequence(task_seq)
    times["loaded"] = time.time()

    program = Thread(target=manager.run, daemon=True)
    program.start()

    print()
    while program.is_alive():
        progress = TaskItem.global_progress()
        sys.stdout.write(
            "\rtime usage: {:.2f}, progress: {:.2f}%: ".format(
                time.time() - times["start"],
                progress * 100
            )
            + "▮" * math.floor(progress * 40)
        )
        sys.stdout.flush()
        sleep(0.1)
    program.join()
    times["end"] = time.time()
    print("Time Used:", times["loaded"] - times["start"])


def main():
    if "multi_agents" in os.listdir(os.getcwd()):
        resource_path = os.path.join(os.getcwd(), "multi_agents", "resources")
    elif "resources" in os.listdir(os.getcwd()):
        resource_path = os.path.join(os.getcwd(), "resources")
    else:
        resource_path = "Not found"
    print("Default path now is " + resource_path)
    if resource_path != "Not found":
        change_resource = input("Do you want to change resource dir? (y/N)")
    else:
        change_resource = "y"
    if change_resource not in ["y", "n", "Y", "N", "yes", "Yes", "no", "No", "", "\n"]:
        print("[ERROR]Invalid input")
    if change_resource == "y":
        resource_path = "Not found"
        resource_path = get_resources_path(resource_path)

    stop = False
    while not stop:
        cmd = input("> ")
        if cmd == "exit":
            stop = True
        elif cmd == "help":
            print(
                "Commands:\n"
                "exit    Exit the system\n"
                "start   Start the simulation\n"
                "  -a    Ignore the agent seq setting and simulate automatically.\n"
                "  -A    Asynchronize tasks loading, only for gigantic simulation\n"
                "  -c [name]   Select a config file in resources directory,\n"
                "              Filetype is not needed. Default value: configs\n"
                "help    Show the help text\n"
            )
        elif cmd.startswith("start ") or cmd == "start":
            args = cmd.split(" ")

            configs = parse_start_cmd(resource_path, args[1:])
            if configs is None:
                print("An error occurred while parsing start command.")
                continue

            run_agents_simulation(resource_path, configs)
        else:
            print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()