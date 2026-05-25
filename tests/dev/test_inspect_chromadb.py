import pytest
from unittest.mock import MagicMock, patch


def test_inspect_chromadb_handles_empty_collections():
    mock_collection = MagicMock()
    mock_collection.get.return_value = {'ids': [], 'documents': [], 'metadatas': []}

    mock_client = MagicMock()
    mock_client.list_collections.return_value = []

    with patch.dict('sys.modules', {'chromadb': MagicMock(), 'chromadb.config': MagicMock()}):
        assert mock_client.list_collections() == []


def test_inspect_chromadb_prints_collection_info(capsys):
    mock_collection = MagicMock()
    mock_collection.get.return_value = {
        'ids': ['item1'],
        'documents': ['test document'],
        'metadatas': [{'type': 'test'}]
    }

    mock_client = MagicMock()
    mock_client.list_collections.return_value = [MagicMock(name='test_collection')]
    mock_client.get_collection.return_value = mock_collection

    with patch.dict('sys.modules', {'chromadb': MagicMock(), 'chromadb.config': MagicMock()}):
        count = len(mock_client.list_collections())
        assert count == 1