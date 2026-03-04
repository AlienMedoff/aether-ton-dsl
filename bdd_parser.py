"""
orchestrator/bdd_parser.py — BDD Feature File Parser
"""

import re
from pathlib import Path


class BDDParser:
    def __init__(self):
        self.patterns = [
            (re.compile(r"Given wallet balance is (?P<amount>\d+) TON"),
             "StateValidatorAgent", {"action": "check"}),
            (re.compile(r"When send (?P<amount>\d+) TON to (?P<recipient>[\w]+)"),
             "TransactionExecutorAgent", {"action": "send_transaction"}),
            (re.compile(r"Then balance is (?P<amount>\d+) TON"),
             "VerificationAgent", {"action": "verify"}),
        ]

    def parse_file(self, file_path: str) -> list:
        return self.parse(Path(file_path).read_text())

    def parse(self, text: str) -> list:
        steps = []
        for line in text.splitlines():
            line = line.strip()
            if not line or not line.startswith(("Given", "When", "Then")):
                continue
            for regex, agent, template in self.patterns:
                m = regex.match(line)
                if m:
                    steps.append({"text": line, "agent": agent,
                                  "payload": {**template, **m.groupdict()}})
                    break
        return steps
