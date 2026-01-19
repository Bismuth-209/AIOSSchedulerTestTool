import datetime
import os
import random
import time
from threading import Thread
from time import sleep
from typing import List, Dict, Any

import yaml

from multi_agents.agent import Agent


class AgentManager:
    def __init__(self, base_path: str, output_path: str, configs: Dict[str, Any]):
        self.base_path = base_path
        self.output_path = output_path
        self.automatic: bool = configs.get("automatic", True)
        self.async_load_tasks: bool = configs.get("async_load_tasks", False)

        self.agents: Dict[str, Agent] = {}
        self.agent_loaders = []

        self.task_seq: List[str] = []

    def load_agents(self, agent_list: List[str] = None):
        if agent_list is None:
            agent_list = os.listdir(self.base_path)
        for agent_name in agent_list:
            if not agent_name.endswith(".yml"):
                continue
            agent_name = agent_name[:-4]
            agent, loader = self.load_agent(agent_name)
            self.agents[agent_name] = agent
            self.agent_loaders.append(loader)

    def load_agent(self, agent_name: str):
        agent_path = os.path.join(self.base_path, agent_name + ".yml")  # agent task input
        agent_output_path = os.path.join(self.output_path, agent_name + ".out") # agent task output
        agent = Agent(agent_name, agent_output_path, self.automatic)

        def load_agent_task():
            with open(agent_path, 'r', encoding="utf-8") as f:
                tasks = yaml.safe_load(f)
                task_num = len(tasks)
                # todo: asynchronized task loading
                for i in range(task_num):
                    task_args = tasks[i]
                    agent.add_task(index=i, content=task_args)
            agent.finish_task_import()

        return agent, load_agent_task

    def load_task_sequence(self, seq: List[str]):
        for agent_name in seq:
            if self.agents.get(agent_name) is None:
                raise RuntimeError(f"Agent {agent_name} is not loaded")
            self.task_seq.append(agent_name)

    def run(self):
        if self.async_load_tasks:
            loader_tasks = []
            for agent_loader in self.agent_loaders:
                task = Thread(target=agent_loader, daemon=True)
                task.start()
                loader_tasks.append(task)
        else:
            for agent_loader in self.agent_loaders:
                agent_loader()
            print(f"[INFO]{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: Tasks loaded!")

        agent_runners = []
        if not self.automatic:
            invalid_agents: set[str] = set()
            tasks = []
            for agent_name in self.task_seq:
                if agent_name in invalid_agents:
                    continue

                agent_target = self.agents[agent_name]

                timer = time.time()
                agent_invalid = False
                while agent_target.is_doing_task() or not agent_target.have_task_to_do():
                    sleep(0.1)
                    if time.time() - timer > 300:
                        agent_invalid = True
                        invalid_agents.add(agent_name)
                        break
                if agent_invalid:
                    continue

                task = Thread(target=agent_target.consume_task, daemon=True)
                task.start()
                tasks.append(task)

                # sleep(random.random() * 3)

            for task in tasks:
                task.join()

        for agent_name, agent in self.agents.items():
            task = Thread(target=agent.automatic_consume_task, daemon=True)
            task.start()
            agent_runners.append(task)

        for agent in agent_runners:
            agent.join()
