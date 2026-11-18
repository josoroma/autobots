"""The service has no embedding or reranking client: memory is lexical retrieval only (US-8.1, and SPECS.md's
non-goals: no hidden embedding or reranking service).

A source scan, so it runs here rather than on a disposable database. tests/db/checks/memory_check.py ran it as
the case 'the service code has no embedding or reranking client' until refactor plan R-66 (TDBC-10).
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICE_SOURCE = ROOT / 'services/agent/src/autobots'
WORDS = ('embedding', 'rerank', 'pgvector', 'vectorstore')
# The one sentence that names them to say they are absent.
STATED_ABSENCE = 'no embedding or reranking'


def found_words(source: Path) -> list[str]:
    return sorted({word for path in source.rglob('*.py') for word in WORDS
                   if word in path.read_text().lower().replace(STATED_ABSENCE, '')})


class NoEmbeddingClient(unittest.TestCase):
    def test_the_service_code_has_no_embedding_or_reranking_client(self) -> None:
        self.assertEqual(found_words(SERVICE_SOURCE), [])

    def test_a_client_would_be_found(self) -> None:
        # The scan must see one, or its pass above shows nothing.
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'memory.py').write_text('# no embedding or reranking here\nfrom vectors import PGVector as pgvector\n')
            self.assertEqual(found_words(Path(folder)), ['pgvector'])


if __name__ == '__main__':
    unittest.main()
