import pytest

from app.models.event import SourceType
from app.parsers import BaseParser, ParserRegistry, UnsupportedParserError, default_registry
from app.parsers.linux_auth_parser import LinuxAuthParser
from app.parsers.network_log_parser import NetworkLogParser
from app.parsers.web_log_parser import WebLogParser
from app.parsers.windows_event_parser import WindowsEventParser


@pytest.mark.parametrize("source_type, cls", [
    ("linux_auth", LinuxAuthParser),
    ("web_application", WebLogParser),
    ("windows_event", WindowsEventParser),
    ("network", NetworkLogParser),
])
def test_correct_parser_selected(source_type, cls):
    assert isinstance(default_registry().get_parser(source_type), cls)


def test_aliases_and_case_follow_event_normalization():
    registry = default_registry()
    assert isinstance(registry.get_parser("Linux-Auth"), LinuxAuthParser)
    assert isinstance(registry.get_parser("windows"), WindowsEventParser)
    assert isinstance(registry.get_parser("web"), WebLogParser)


@pytest.mark.parametrize("value", ["firewall", "", "application", "../etc/passwd"])
def test_unsupported_type(value):
    with pytest.raises(UnsupportedParserError) as exc:
        default_registry().get_parser(value)
    assert "linux_auth" in exc.value.supported


def test_every_parser_source_type_is_a_valid_event_source():
    registry = default_registry()
    for source_type in registry.supported_source_types():
        assert source_type in {s.value for s in SourceType}
        assert isinstance(registry.get_parser(source_type), BaseParser)


def test_new_parser_registers_without_touching_others():
    class Dummy(BaseParser):
        source_type = "application"

        def parse(self, raw_log):
            return {}

    registry = default_registry()
    registry.register(Dummy())
    assert isinstance(registry.get_parser("application"), Dummy)
    assert isinstance(registry.get_parser("linux_auth"), LinuxAuthParser)
    assert ParserRegistry().supported_source_types() == []
