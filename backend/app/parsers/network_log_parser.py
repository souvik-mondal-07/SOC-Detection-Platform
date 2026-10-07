"""Simple structured network connection logs: a JSON object, or one CSV line with
the columns

  timestamp,source_ip,destination_ip,source_port,destination_port,protocol,action,status

Required: source_ip, destination_ip, destination_port, protocol. Everything else
is optional. This parser only records connections; it does not look for scans.
"""

import csv
from collections.abc import Mapping
from typing import Any

from app.parsers.base import BaseParser, ParsedEvent, ParseError, clip_message, present, require_mapping

CSV_COLUMNS = ("timestamp", "source_ip", "destination_ip", "source_port", "destination_port", "protocol", "action", "status")
REQUIRED = ("source_ip", "destination_ip", "destination_port", "protocol")

_STATUS_MAP = {
    "allowed": "success", "allow": "success", "accept": "success", "accepted": "success",
    "permit": "success", "permitted": "success", "success": "success",
    "denied": "blocked", "deny": "blocked", "drop": "blocked", "dropped": "blocked",
    "blocked": "blocked", "block": "blocked", "reject": "blocked", "rejected": "blocked",
    "failed": "failed", "fail": "failed",
}


def _port(value: Any, field: str) -> int:
    try:
        port = int(str(value).strip())
    except ValueError:
        raise ParseError("invalid_field", f"{field} must be a number between 0 and 65535", field) from None
    if isinstance(value, bool) or not 0 <= port <= 65535:
        raise ParseError("invalid_field", f"{field} must be a number between 0 and 65535", field)
    return port


class NetworkLogParser(BaseParser):
    source_type = "network"

    def parse(self, raw_log: str | Mapping[str, Any]) -> ParsedEvent:
        record = self._record(raw_log)
        for field in REQUIRED:
            if present(record.get(field)) is None:
                raise ParseError("missing_field", f"{field} is required", field)

        protocol = str(record["protocol"]).strip().upper()
        if not protocol.isalnum() or len(protocol) > 16:
            raise ParseError("invalid_field", "protocol must be a short alphanumeric name such as TCP", "protocol")

        metadata: dict[str, Any] = {
            "destination_ip": str(record["destination_ip"]).strip(),
            "destination_port": _port(record["destination_port"], "destination_port"),
            "protocol": protocol,
        }
        if (source_port := present(record.get("source_port"))) is not None:
            metadata["source_port"] = _port(source_port, "source_port")

        raw_status = present(record.get("status"))
        status = _STATUS_MAP.get(str(raw_status).strip().lower(), "unknown") if raw_status is not None else "unknown"
        action = present(record.get("action")) or "connection"

        source_ip = str(record["source_ip"]).strip()
        source = f"{source_ip}:{metadata['source_port']}" if "source_port" in metadata else source_ip
        outcome = f" {str(raw_status).strip().lower()}" if raw_status is not None else ""
        message = f"Connection{outcome}: {source} -> {metadata['destination_ip']}:{metadata['destination_port']} {protocol}"

        return {
            "timestamp": present(record.get("timestamp")),
            "source": self.source_type,
            "event_type": "network",
            "action": action,
            "status": status,
            "source_ip": source_ip,
            "message": clip_message(message),
            "metadata": metadata,
        }

    @staticmethod
    def _record(raw_log: Any) -> dict[str, Any]:
        if isinstance(raw_log, str) and not raw_log.lstrip().startswith("{"):
            try:
                row = next(csv.reader([raw_log.strip()]))
            except (csv.Error, StopIteration):
                raise ParseError("invalid_log", "Input is not a valid CSV line") from None
            if not raw_log.strip() or len(row) != len(CSV_COLUMNS):
                raise ParseError("invalid_log", f"CSV line must have exactly {len(CSV_COLUMNS)} columns: {','.join(CSV_COLUMNS)}")
            return dict(zip(CSV_COLUMNS, (cell.strip() for cell in row)))
        return require_mapping(raw_log, "network log")
