import datetime
import json
import queue
import random
import time
from enum import Enum
from queue import Queue
from time import sleep
from typing import Dict, List, Any

from cerebrum.llm.apis import (
    llm_chat, llm_chat_with_json_output, llm_chat_with_tool_call_output, llm_call_tool,
    llm_operate_file
)
from cerebrum.memory.apis import (
    create_memory, get_memory, update_memory, delete_memory,
    search_memories, create_agentic_memory
)
from cerebrum.storage.apis import (
    mount, # todo
)


random.seed(time.time_ns())


TASK_TYPE_FUNCS = {
    "chat": llm_chat,
    "chat_json": llm_chat_with_json_output,
    "chat_tool": llm_chat_with_tool_call_output,
    "tool": llm_call_tool,
    "file_op": llm_operate_file,
    "mem_create": create_memory,
    "mem_get": get_memory,
    "mem_update": update_memory,
    "mem_delete": delete_memory,
    "mem_search": search_memories,
    "mem_create_agentic": create_agentic_memory,
    "mount": mount,
}


class TaskType(Enum):
    CHAT = "chat"
    CHAT_JSON = "chat_json"
    CHAT_TOOL_CALL = "chat_tool"
    TOOL = "tool"
    FILE_OP = "file_op"
    MEM_CREATE = "mem_create"
    MEM_GET = "mem_get"
    MEM_UPDATE = "mem_update"
    MEM_DELETE = "mem_delete"
    MEM_SEARCH = "mem_search"
    AGENTIC_MEM_CREATE = "mem_create_agentic"
    MOUNT = "mount"
    # todo: storage
    # todo: other type api

    def get_func(self):
        return TASK_TYPE_FUNCS[self.value]

    def is_llm_api(self):
        return self.value in ["chat", "chat_json", "chat_tool", "tool", "file_op"]

    def is_mem_api(self):
        return self.value in ["mem_create", "mem_get", "mem_update", "mem_delete", "mem_search", "mem_create_agentic"]

    def is_new_mem_api(self):
        return self.value in ["mem_create", "mem_create_agentic"]

    def is_visiting_existed_mem_api(self):
        return self.value in ["mem_get", "mem_update", "mem_delete"]

    def is_storage_api(self):
        return self.value in ["mount"]

class TaskItem:
    TASK_NUMBER = 0
    TASK_FINISHED = 0

    def __init__(
            self,
            agent_name: str,
            task_type: TaskType,
            content: Dict[str, Any],
            index: int
    ):
        self.agent_name: str = agent_name
        self.task_type: TaskType = task_type
        self.content: Dict[str, Any] = content
        self.index: int = index
        self.time_interval: float = content.get("time_interval", 0.0)

        self.start_time: float = time.time()
        self.end_time: float = -1.0

        self.response = ""
        TaskItem.TASK_NUMBER += 1

    def add_response(self, response: str):
        self.response = response
        self.end_time = time.time()
        TaskItem.TASK_FINISHED += 1

    @classmethod
    def global_progress(cls):
        if cls.TASK_NUMBER == 0:
            return 0
        return cls.TASK_FINISHED / cls.TASK_NUMBER


class Agent:
    def __init__(self, name: str, output_file: str, automatic: bool, system_prompt: str = ""):
        self.name = name
        with open(output_file, "w"):
            pass
        self.output_file: str = output_file
        self.automatic: bool = automatic

        self.task_list: Queue[TaskItem] = Queue()
        self.done_tasks: list[TaskItem] = []
        self.task_number: int = 0
        self.task_done: int = 0

        self.running = False
        self.task_import_done = False
        self.shutdown = False
        self.task_lost = False

        self.messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}] if system_prompt else []
        self.memories: List[str] = []

    def send_request(self, func_type: TaskType, **kwargs):
        args = {k: v for k, v in kwargs.items()}
        args["agent_name"] = self.name
        if func_type.is_llm_api():
            load_history = args.get("with_history", True)
            if load_history:
                self.messages.append({"role": "user", "content": args.get("messages", "")})
                # todo: change to use agent rather than operating file
                args.pop("messages", None)
                args["messages"] = [x for x in self.messages]
            args.pop("with_history", None)
        elif func_type.is_mem_api():
            if (func_type.is_visiting_existed_mem_api()
                and (kwargs.get("memory_id") is None or kwargs.get("memory_id") not in self.memories)):
                with open(self.output_file, "a", encoding="utf-8") as f:
                    f.write(
                        f"[Warning]{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"  Agent '{self.name}' try visit non-exist memory.\n"
                        f"  Target memory id: {kwargs.get('memory_id', 'id not provided')}\n"
                        f"  Existed memories' ids: {str(*self.memories)}\n"
                        "\n"
                    )
        response = func_type.get_func()(**args)
        if func_type.is_llm_api():
            self.messages.append({"role": "assistant", "content": response})
        elif func_type.is_mem_api():
            try:
                response_json = json.loads(response)
            except json.decoder.JSONDecodeError:
                with open(self.output_file, "a", encoding="utf-8") as f:
                    f.write(
                        f"[Warning]{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"  Agent '{self.name}' memory operation get a non-json response.\n"
                        "\n"
                    )
                response_json = {"success": False}
            if (func_type.is_new_mem_api()
                and response_json.get("success", False) and response_json.get("memory_id") is not None):
                self.memories.append(response_json.get("memory_id"))
            if (func_type.value == TaskType.MEM_DELETE.value
                    and response_json.get("success", False)
                    and args.get("memory_id") in self.memories):
                self.memories.remove(args.get("memory_id"))
        return response

    def add_task(self, index: int, content: Dict[str, Any] = None, task: TaskItem = None):
        if task:
            self.task_list.put(task)
        elif content:
            task_type = TaskType(content.get("task_type", "chat"))
            content.pop("task_type", None)
            self.task_list.put(TaskItem(
                agent_name=self.name,
                task_type=task_type,
                content=content,
                index=index
            ))
        else:
            raise ValueError("Either a task or a command must be provided")
        self.task_number += 1

    def consume_task(self):
        self.running = True
        if self.task_import_done and self.task_list.empty():
            with open(self.output_file, "a", encoding="utf-8") as f:
                f.write(
                    f"[Exception]{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"  Agent '{self.name}' has no task to consume.\n"
                    f"  All task num: {self.task_number}; Finished task num: {self.task_done}\n"
                    "\n"
                )
            return
        try:
            task = self.task_list.get(timeout=10)
        except queue.Empty:
            with open(self.output_file, "a", encoding="utf-8") as f:
                f.write(
                    f"[Warning]{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"  Agent '{self.name}' waited for 10 seconds but still hasn't received any new tasks.\n"
                    f"  All task num: {self.task_number}; Finished task num: {self.task_done}\n"
                    "\n"
                )
            task = self.task_list.get()

        with open(self.output_file, "a", encoding="utf-8") as f:
            f.write(
                f"[Info]{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"  Task {task.index} of agent {self.name} start.\n"
                f"  Task info: {str(task)}\n"
                "\n"
            )

        response = self.send_request(task.task_type, **task.content)
        task.add_response(response)

        self.done_tasks.append(task)
        with open(self.output_file, "a", encoding="utf-8") as f:
            f.write(
                f"[Info]{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"  Task {task.index} of agent {self.name} done.\n"
                f"  Response:\n"
            )
            f.write(str(response))
            f.write("\n")
            if task.task_type.is_mem_api():
                f.write(f"  Memories Now: {str(*self.memories)}\n")
            f.write("\n")
        self.task_done += 1
        self.running = False

        # if task.time_interval > 0 or self.automatic:
        #     if task.time_interval > 0:
        #         time_interval = task.time_interval
        #     elif self.done_tasks:
        #         time_interval = random.random() * max(self.done_tasks[-1].end_time - self.done_tasks[-1].start_time, 10)
        #     else:
        #         time_interval = random.random() * 10
        #     sleep(time_interval)

    def have_task_to_do(self):
        return not self.task_list.empty()

    def is_doing_task(self):
        return self.running

    def finish_task_import(self):
        self.task_import_done = True

    def do_shutdown(self):
        with open(self.output_file, "a", encoding="utf-8") as f:
            f.write(
                f"[Info]{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: Agent shutdown\n"
                f"  History messages:\n"
            )
            for msg in self.messages:
                f.write(str(msg) + "\n")
            f.write(
                "\n"
                f"  Allocated memories: {str(*self.memories)}\n"
            )
            f.write("\n")
        self.shutdown = True

    def automatic_consume_task(self):
        # sleep(random.random() * 5)
        while not self.shutdown:
            self.consume_task()
            if self.task_import_done and not self.have_task_to_do():
                self.do_shutdown()
