"""Tests for the stream module."""

from __future__ import annotations

import io

import pytest

from logtally.stream import stream_lines


def test_stream_lines_from_file(tmp_path):
    f = tmp_path / "x.log"
    f.write_text("line one\nline two\nline three\n")
    result = list(stream_lines(f))
    assert result == ["line one", "line two", "line three"]


def test_stream_lines_handles_no_trailing_newline(tmp_path):
    f = tmp_path / "x.log"
    f.write_text("line one\nline two")
    result = list(stream_lines(f))
    assert result == ["line one", "line two"]


def test_stream_lines_handles_empty_file(tmp_path):
    f = tmp_path / "x.log"
    f.write_text("")
    result = list(stream_lines(f))
    assert result == []


def test_stream_lines_raises_for_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="not found"):
        list(stream_lines(tmp_path / "does-not-exist.log"))


def test_stream_lines_tolerates_bad_bytes(tmp_path):
    f = tmp_path / "x.log"
    f.write_bytes(b"valid line\n\xff\xfe garbage\nanother valid\n")
    result = list(stream_lines(f))
    assert len(result) == 3
    assert result[0] == "valid line"
    assert result[2] == "another valid"


def test_stream_lines_from_stdin(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("a\nb\nc\n"))
    result = list(stream_lines("-"))
    assert result == ["a", "b", "c"]


def test_stream_lines_none_means_stdin(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("x\ny\n"))
    result = list(stream_lines(None))
    assert result == ["x", "y"]
