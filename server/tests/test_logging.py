"""Tests for the server logging configuration."""

import gzip
import logging
import tempfile
import unittest
from pathlib import Path

from app.core.settings import LoggingSettings
from logs import configure_logging, log


class LoggingConfigurationTest(unittest.TestCase):
    """Verify file output, standard logging interception, and rotation."""

    def test_file_logging_and_compressed_rotation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir) / "nested" / "logs"
            config = LoggingSettings(
                level="DEBUG",
                directory=log_dir,
                file_name="server.log",
                rotation="1 KB",
                retention="1 day",
                compression="gz",
                console=False,
            )

            log_path = configure_logging(config)
            log.debug("debug-marker")
            logging.getLogger("test.standard").info("standard-marker")
            for index in range(30):
                log.info("rotation-marker-{} {}", index, "x" * 100)
            log.complete()

            self.assertEqual(log_path, log_dir / "server.log")
            self.assertTrue(log_path.exists())

            compressed_logs = list(log_dir.glob("*.gz"))
            self.assertTrue(compressed_logs)

            content = log_path.read_text(encoding="utf-8")
            for compressed_log in compressed_logs:
                with gzip.open(
                    compressed_log, mode="rt", encoding="utf-8"
                ) as stream:
                    content += stream.read()

            self.assertIn("debug-marker", content)
            self.assertIn("standard-marker", content)
            self.assertIn("rotation-marker", content)


if __name__ == "__main__":
    unittest.main()
