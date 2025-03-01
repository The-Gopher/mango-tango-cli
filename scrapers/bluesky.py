import multiprocessing
import signal
import time
from collections import defaultdict
from csv import writer
from dataclasses import dataclass
from datetime import datetime
from types import FrameType
from typing import Any, Generator

import atproto_client.models.app.bsky.feed.post
from atproto import (
    CAR,
    AtUri,
    FirehoseSubscribeReposClient,
    firehose_models,
    models,
    parse_subscribe_repos_message,
)

# Inspired by (good reference) https://raw.githubusercontent.com/MarshalX/atproto/main/examples/firehose/process_commits.py


_INTERESTED_RECORDS = {
    models.ids.AppBskyFeedPost: models.AppBskyFeedPost,
}


def _get_ops_by_type(commit: models.ComAtprotoSyncSubscribeRepos.Commit) -> defaultdict:
    operation_by_type = defaultdict(lambda: {"created": [], "deleted": []})

    car = CAR.from_bytes(commit.blocks)
    for op in commit.ops:
        if op.action == "update":
            # not supported yet
            continue

        uri = AtUri.from_str(f"at://{commit.repo}/{op.path}")

        if op.action == "create":
            if not op.cid:
                continue

            create_info = {"uri": str(uri), "cid": str(op.cid), "author": commit.repo}

            record_raw_data = car.blocks.get(op.cid)
            if not record_raw_data:
                continue

            record = models.get_or_create(record_raw_data, strict=False)
            record_type = _INTERESTED_RECORDS.get(uri.collection)
            if record_type and models.is_record_type(record, record_type):
                operation_by_type[uri.collection]["created"].append(
                    {"record": record, **create_info}
                )

        if op.action == "delete":
            operation_by_type[uri.collection]["deleted"].append({"uri": str(uri)})

    return operation_by_type


def worker_parse(
    cursor_value: multiprocessing.Value,
    pool_queue: multiprocessing.Queue,
    write_queue: multiprocessing.Queue,
) -> None:
    signal.signal(signal.SIGINT, signal.SIG_IGN)  # we handle it in the main process

    while True:
        message = pool_queue.get()

        commit = parse_subscribe_repos_message(message)
        if not isinstance(commit, models.ComAtprotoSyncSubscribeRepos.Commit):
            continue

        if commit.seq % 20 == 0:
            cursor_value.value = commit.seq

        if not commit.blocks:
            continue

        ops = _get_ops_by_type(commit)
        for created_post in ops[models.ids.AppBskyFeedPost]["created"]:
            author = created_post["author"]
            record = created_post["record"]

            inlined_text = record.text.replace("\n", " ")

            write_queue.put(
                (
                    record.created_at,
                    author,
                    inlined_text,
                    created_post["uri"],
                    created_post["cid"],
                )
            )


def worker_write(write_queue: multiprocessing.Queue) -> None:
    signal.signal(signal.SIGINT, signal.SIG_IGN)  # we handle it in the main process

    with open("bluesky_posts.txt", "w") as f:
        csv_writer = writer(f)
        csv_writer.writerow(["created_at", "author", "text", "uri", "cid"])
        while True:
            line = write_queue.get()
            csv_writer.writerow(line)


def get_firehose_params(
    cursor_value: multiprocessing.Value,
) -> models.ComAtprotoSyncSubscribeRepos.Params:
    return models.ComAtprotoSyncSubscribeRepos.Params(cursor=cursor_value.value)


def measure_events_per_second(func: callable) -> callable:
    def wrapper(*args) -> Any:
        wrapper.calls += 1
        cur_time = time.time()

        if cur_time - wrapper.start_time >= 1:
            print(f"NETWORK LOAD: {wrapper.calls} events/second")
            wrapper.start_time = cur_time
            wrapper.calls = 0

        return func(*args)

    wrapper.calls = 0
    wrapper.start_time = time.time()

    return wrapper


def signal_handler(_: int, __: FrameType) -> None:
    print(
        "Keyboard interrupt received.\nWaiting for the queue to empty before terminating processes..."
    )

    # Stop receiving new messages
    client.stop()

    # Drain the messages queue
    while not parse_queue.empty():
        print("Waiting for the parse queue to empty...")
        time.sleep(0.2)

    print("Parse queue is empty. Gracefully terminating processes...")

    pool.terminate()
    pool.join()

    while not write_queue.empty():
        print("Waiting for the write queue to empty...")
        time.sleep(0.2)

    print("Write queue is empty. Gracefully terminating processes...")

    writer_processes.terminate()
    writer_processes.join()

    exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)

    start_cursor = None

    params = None
    cursor = multiprocessing.Value("i", 0)
    if start_cursor is not None:
        cursor = multiprocessing.Value("i", start_cursor)
        params = get_firehose_params(cursor)

    client = FirehoseSubscribeReposClient(params)

    workers_count = multiprocessing.cpu_count() * 2 - 1
    max_queue_size = 10000

    parse_queue = multiprocessing.Queue(maxsize=max_queue_size)
    write_queue = multiprocessing.Queue()

    pool = multiprocessing.Pool(
        workers_count, worker_parse, (cursor, parse_queue, write_queue)
    )

    writer_processes = multiprocessing.Process(target=worker_write, args=(write_queue,))
    writer_processes.start()

    @measure_events_per_second
    def on_message_handler(message: firehose_models.MessageFrame) -> None:
        if cursor.value:
            # we are using updating the cursor state here because of multiprocessing
            # typically you can call client.update_params() directly on commit processing
            client.update_params(get_firehose_params(cursor))

        parse_queue.put(message)

    client.start(on_message_handler)
