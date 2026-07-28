import os
import socket
import ray
import sys


def main():
    ray.init(address="auto")

    print_local_env("in main")
    ref = remote_call.remote(1,2)
    result = ray.get(ref)

    print(f"result: {result}")

@ray.remote
def remote_call(a: int,b: int) -> int:
    print_local_env("in remote call")
    return a+b

def print_local_env(name: str):
    local_hostname = socket.gethostname()
    local_pid = os.getpid()

    print(f"{name}: {local_hostname}:{local_pid}")

if __name__ == '__main__':
    main()