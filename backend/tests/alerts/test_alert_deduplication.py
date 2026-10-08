from tests.alerts.conftest import make


def test_separate_bursts_create_separate_alerts(service, event_repo, alert_repo):
    first = [make(i) for i in range(5)]
    second = [make(3600 + i) for i in range(5)]  # an hour later, no shared events
    event_repo.create_many(first + second)
    assert len(service.generate_for_event_id(first[-1].event_id).created) == 1
    assert len(service.generate_for_event_id(second[-1].event_id).created) == 1
    assert alert_repo.get_alerts()[1] == 2


def test_different_source_ips_not_deduplicated(service, event_repo):
    a = [make(i, source_ip="10.1.1.1") for i in range(5)]
    b = [make(i, source_ip="10.2.2.2") for i in range(5)]
    event_repo.create_many(a + b)
    assert len(service.generate_for_event_id(a[-1].event_id).created) == 1
    assert len(service.generate_for_event_id(b[-1].event_id).created) == 1


def test_repeated_evaluation_many_times(service, burst, alert_repo):
    for _ in range(10):
        service.generate_for_event_id(burst[-1].event_id)
    assert alert_repo.get_alerts()[1] == 1
