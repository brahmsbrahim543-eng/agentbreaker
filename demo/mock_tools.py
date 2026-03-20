"""Mock tools for AgentBreaker demos.

Each tool simulates a specific failure mode that AgentBreaker detects:
- MockSearchTool: semantically similar results -> Similarity Detector
- MockFailingTool: repeated connection errors -> Error Cascade Detector
- MockExpensiveTool: exponentially growing cost -> Cost Velocity Tracker
"""

import random


class MockSearchTool:
    """Simulates web search returning similar results about the same topic.
    Results vary slightly in wording but convey the same information,
    triggering the Similarity Detector."""

    TEMPLATES = [
        "Scientists estimate there are roughly {n} stars in the observable universe, according to {src}.",
        "Based on data from {src}, astronomers believe approximately {n} stars exist in the known universe.",
        "Current research published by {src} suggests the total star count is around {n}.",
        "The latest astronomical surveys by {src} indicate there could be as many as {n} stars.",
        "According to recent findings from {src}, the estimated number of stars stands at roughly {n}.",
        "A comprehensive study by {src} places the number of observable stars at approximately {n}.",
        "Data compiled by {src} shows the universe contains an estimated {n} stars in total.",
    ]

    NUMBERS = [
        "200 billion trillion",
        "200 sextillion",
        "2\u00d710\u00b2\u00b3",
        "roughly 10\u00b2\u2074",
        "two hundred billion trillion",
        "about 200,000,000,000,000,000,000,000",
    ]

    SOURCES = [
        "NASA",
        "ESA",
        "the Hubble Space Telescope",
        "the James Webb Space Telescope",
        "a 2024 Nature study",
        "the European Southern Observatory",
        "recent sky surveys",
        "the Sloan Digital Sky Survey",
    ]

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.call_count = 0

    def run(self, query: str) -> str:
        self.call_count += 1
        template = self.TEMPLATES[self.call_count % len(self.TEMPLATES)]
        return template.format(
            n=self.rng.choice(self.NUMBERS),
            src=self.rng.choice(self.SOURCES),
        )


class MockFailingTool:
    """Tool that always fails with a connection error.
    Triggers the Error Cascade Detector."""

    def __init__(self):
        self.call_count = 0

    def run(self, query: str) -> str:
        self.call_count += 1
        raise ConnectionError(
            f"ConnectionTimeout: pricing-service.internal:443 "
            f"- service unavailable (attempt {self.call_count})"
        )


class MockExpensiveTool:
    """Tool whose cost doubles each call.
    Triggers the Cost Velocity Tracker."""

    def __init__(self):
        self.call_count = 0

    def run(self, query: str) -> str:
        self.call_count += 1
        records = 100 * (2 ** self.call_count)
        return (
            f"Analysis complete. Processed {records:,} records from the database. "
            f"Found {self.call_count * 3} anomalies requiring further investigation."
        )
