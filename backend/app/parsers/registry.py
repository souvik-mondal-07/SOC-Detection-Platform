"""Maps a source type to its parser. New parsers are added here with one line."""

from app.models.normalization import normalize_source
from app.parsers.base import BaseParser
from app.parsers.linux_auth_parser import LinuxAuthParser
from app.parsers.network_log_parser import NetworkLogParser
from app.parsers.web_log_parser import WebLogParser
from app.parsers.windows_event_parser import WindowsEventParser


class UnsupportedParserError(Exception):
    def __init__(self, source_type: str, supported: list[str]) -> None:
        super().__init__(f"No parser for source type '{source_type}'")
        self.source_type = source_type
        self.supported = supported


class ParserRegistry:
    def __init__(self, parsers: list[BaseParser] | None = None) -> None:
        self._parsers: dict[str, BaseParser] = {}
        for parser in parsers or []:
            self.register(parser)

    def register(self, parser: BaseParser) -> None:
        self._parsers[parser.source_type] = parser

    def supported_source_types(self) -> list[str]:
        return sorted(self._parsers)

    def get_parser(self, source_type: str) -> BaseParser:
        # Same canonicalisation as events, so "Linux-Auth" and "windows" behave as expected.
        key = normalize_source(source_type)
        parser = self._parsers.get(key) if isinstance(key, str) else None
        if parser is None:
            raise UnsupportedParserError(str(source_type)[:64], self.supported_source_types())
        return parser


def default_registry() -> ParserRegistry:
    return ParserRegistry([LinuxAuthParser(), WebLogParser(), WindowsEventParser(), NetworkLogParser()])
