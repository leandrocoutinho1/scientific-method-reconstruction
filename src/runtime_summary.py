import time


def start_timer() -> float:
    return time.perf_counter()


def print_runtime_summary(
    *,
    start_time: float,
    total_items: int,
    processed_items: int,
    errors: int = 0,
    skipped: int = 0,
    item_label: str = "items",
) -> None:
    runtime = time.perf_counter() - start_time
    speed = processed_items / runtime if runtime else 0
    throughput = runtime / processed_items if processed_items else 0

    print(f"Processing completed: {processed_items} out of {total_items} {item_label} processed")

    if skipped:
        print(f"Skipped: {skipped} out of {total_items} {item_label}")

    print(f"Errors: {errors} out of {total_items} {item_label}")
    print(f"⏱️  Total runtime: {runtime:.2f} seconds")
    print(f"🚀 Speed: {speed:.2f} {item_label}/second")
    print(f"   Throughput: {throughput:.2f} seconds/{item_label.rstrip('s')}")
