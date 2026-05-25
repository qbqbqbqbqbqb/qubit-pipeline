import pytest
from pathlib import Path
from src.utils.file_utills import (
    load_text_file,
    load_json_file,
    check_file_exists,
    get_file_path,
    get_root,
    load_word_list,
    load_phrases,
)


def test_check_file_exists_false_for_none():
    assert check_file_exists(None) is False


def test_check_file_exists_false_for_missing(tmp_path):
    missing = tmp_path / "nonexistent.txt"
    assert check_file_exists(missing) is False


def test_check_file_exists_true_for_existing(tmp_path):
    existing = tmp_path / "exists.txt"
    existing.write_text("content")
    assert check_file_exists(existing) is True


def test_get_file_path(tmp_path):
    p = get_file_path(tmp_path, "foo.txt")
    assert p.name == "foo.txt"
    assert p.parent == tmp_path.resolve()


def test_get_root_returns_path():
    root = get_root()
    assert root.exists()
    assert (root / "src").exists() or (root / "tests").exists()


def test_load_text_file(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.write_text("hello world", encoding="utf-8")
    content = load_text_file(file_path)
    assert content == "hello world"


def test_load_text_file_raises_on_missing(tmp_path):
    missing = tmp_path / "missing.txt"
    with pytest.raises(Exception):
        load_text_file(missing)


def test_load_json_file(tmp_path):
    json_path = tmp_path / "test.json"
    json_path.write_text('{"key": "value"}')
    data = load_json_file(str(json_path))
    assert data == {"key": "value"}


def test_load_json_file_raises_on_invalid(tmp_path):
    json_path = tmp_path / "invalid.json"
    json_path.write_text("not valid json")
    with pytest.raises(Exception):
        load_json_file(str(json_path))


def test_load_word_list(tmp_path):
    words_path = tmp_path / "words.txt"
    words_path.write_text("Hello\nWorld\n123Test\n!")
    words = load_word_list(words_path)
    assert words == ["hello", "world", "test"]


def test_load_word_list_empty_file(tmp_path):
    words_path = tmp_path / "empty.txt"
    words_path.write_text("")
    words = load_word_list(words_path)
    assert words == []


def test_load_phrases(tmp_path):
    phrases_path = tmp_path / "phrases.txt"
    phrases_path.write_text("phrase one\nphrase two\n")
    phrases = load_phrases(phrases_path)
    assert phrases == ["phrase one", "phrase two"]


def test_load_phrases_empty_file(tmp_path):
    phrases_path = tmp_path / "empty.txt"
    phrases_path.write_text("")
    phrases = load_phrases(phrases_path)
    assert phrases == []
