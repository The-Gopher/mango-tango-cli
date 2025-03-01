from atproto import (
    CAR,
    FirehoseSubscribeReposClient,
    firehose_models,
    models,
    AtUri,
    parse_subscribe_repos_message,
)

import atproto_client.models.app.bsky.feed.post


def dump_from_firehose3():
    client = FirehoseSubscribeReposClient()

    def on_message_handler(message: firehose_models.MessageFrame) -> None:
        commit = parse_subscribe_repos_message(message)

        if not isinstance(commit, models.ComAtprotoSyncSubscribeRepos.Commit):
            return

        ops = _get_ops_by_type(commit)
        if not ops["posts"]["created"]:
            return

        for post in ops["posts"]["created"]:
            record: atproto_client.models.app.bsky.feed.post.Record = post["record"]
            print(record.text)

    client.start(on_message_handler)


# Copied from https://raw.githubusercontent.com/MarshalX/atproto/main/examples/firehose/process_commits.py
def _get_ops_by_type(  # noqa: C901, E302
    commit: models.ComAtprotoSyncSubscribeRepos.Commit,
) -> dict:  # noqa: C901, E302
    operation_by_type = {
        "posts": {"created": [], "deleted": []},
        "reposts": {"created": [], "deleted": []},
        "likes": {"created": [], "deleted": []},
        "follows": {"created": [], "deleted": []},
    }

    car = CAR.from_bytes(commit.blocks)
    for op in commit.ops:
        uri = AtUri.from_str(f"at://{commit.repo}/{op.path}")

        if op.action == "update":
            # not supported yet
            continue

        if op.action == "create":
            if not op.cid:
                continue

            create_info = {"uri": str(uri), "cid": str(op.cid), "author": commit.repo}

            record_raw_data = car.blocks.get(op.cid)
            if not record_raw_data:
                continue

            record = firehose_models.get_or_create(record_raw_data, strict=False)
            if uri.collection == models.ids.AppBskyFeedLike and models.is_record_type(
                record, models.ids.AppBskyFeedLike
            ):
                operation_by_type["likes"]["created"].append(
                    {"record": record, **create_info}
                )
            elif uri.collection == models.ids.AppBskyFeedPost and models.is_record_type(
                record, models.ids.AppBskyFeedPost
            ):
                operation_by_type["posts"]["created"].append(
                    {"record": record, **create_info}
                )
            elif (
                uri.collection == models.ids.AppBskyFeedRepost
                and models.is_record_type(record, models.ids.AppBskyFeedRepost)
            ):
                operation_by_type["reposts"]["created"].append(
                    {"record": record, **create_info}
                )
            elif (
                uri.collection == models.ids.AppBskyGraphFollow
                and models.is_record_type(record, models.ids.AppBskyGraphFollow)
            ):
                operation_by_type["follows"]["created"].append(
                    {"record": record, **create_info}
                )

        if op.action == "delete":
            if uri.collection == models.ids.AppBskyFeedLike:
                operation_by_type["likes"]["deleted"].append({"uri": str(uri)})
            elif uri.collection == models.ids.AppBskyFeedPost:
                operation_by_type["posts"]["deleted"].append({"uri": str(uri)})
            elif uri.collection == models.ids.AppBskyFeedRepost:
                operation_by_type["reposts"]["deleted"].append({"uri": str(uri)})
            elif uri.collection == models.ids.AppBskyGraphFollow:
                operation_by_type["follows"]["deleted"].append({"uri": str(uri)})

    return operation_by_type


if __name__ == "__main__":
    dump_from_firehose3()
