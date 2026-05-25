import sys
import pytest
from unittest.mock import MagicMock, patch


def test_preload_chromadb_models_returns_true_on_success():
    with patch.dict('sys.modules', {'chromadb': MagicMock(), 'chromadb.config': MagicMock()}):
        import importlib
        spec = importlib.util.spec_from_file_location(
            "preload_chromadb",
            "src/dev/preload_chromadb.py"
        )
        preload_module = importlib.util.module_from_spec(spec)

        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_collection.query.return_value = {"ids": ["test"]}
        mock_client.get_or_create_collection.return_value = mock_collection

        with patch('chromadb.PersistentClient', return_value=mock_client):
            with patch('chromadb.config.Settings', return_value=MagicMock()):
                spec.loader.exec_module(preload_module)
                result = preload_module.preload_chromadb_models()
                assert result is True


def test_preload_chromadb_models_returns_false_on_error():
    with patch.dict('sys.modules', {'chromadb': MagicMock(), 'chromadb.config': MagicMock()}):
        import importlib
        spec = importlib.util.spec_from_file_location(
            "preload_chromadb",
            "src/dev/preload_chromadb.py"
        )
        preload_module = importlib.util.module_from_spec(spec)

        with patch('chromadb.PersistentClient', side_effect=Exception("Connection failed")):
            spec.loader.exec_module(preload_module)
            result = preload_module.preload_chromadb_models()
            assert result is False