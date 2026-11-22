"""Manifest verification using only synthetic temporary fixtures.

This test never opens the repository's data directory or evaluates a parser.
"""

import hashlib
import json

import pytest

from evaluate import verify_manifest


def test_manifest_verifies_synthetic_fixture(tmp_path):
    content = b'synthetic manifest verification fixture\n'
    expected = hashlib.sha256(content).hexdigest()
    (tmp_path / 'fixture.bin').write_bytes(content)
    (tmp_path / 'MANIFEST.json').write_text(
        json.dumps({'files': {'fixture.bin': expected}}), encoding='utf-8'
    )
    assert verify_manifest(tmp_path) == {'fixture.bin': expected}


def test_manifest_rejects_modified_synthetic_fixture(tmp_path):
    (tmp_path / 'fixture.bin').write_bytes(b'synthetic changed bytes\n')
    (tmp_path / 'MANIFEST.json').write_text(
        json.dumps({'files': {'fixture.bin': '0' * 64}}), encoding='utf-8'
    )
    with pytest.raises(ValueError, match='dataset file changed: fixture.bin'):
        verify_manifest(tmp_path)
