from app.usage import Usage, collect_usage, record_usage


def test_record_usage_outside_a_collection_does_nothing():
    record_usage("modelo", 10, 5)
    with collect_usage() as usages:
        pass
    record_usage("modelo", 10, 5)
    assert usages == []


def test_collect_usage_gathers_every_call_in_the_block():
    with collect_usage() as usages:
        record_usage("modelo-a", 10, 5)
        record_usage("modelo-b", 7, 3)
    assert usages == [Usage("modelo-a", 10, 5), Usage("modelo-b", 7, 3)]
