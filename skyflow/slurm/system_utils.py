import psutil

def get_free_ram():
    # Get system memory information
    memory_info = psutil.virtual_memory()

    # Get the amount of free RAM in bytes
    free_ram_bytes = memory_info.available

    # Convert bytes to megabytes for readability
    free_ram_gigabytes = free_ram_bytes / (1024 ** 3)

    return free_ram_gigabytes

if __name__ == "__main__":
    free_ram = get_free_ram()
    print(f"Free RAM: {free_ram:.2f} GB")