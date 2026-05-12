"""crm/tests/test_validation.py — Tests AAA para helpers de validación de payload JSON."""

from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

from crm.views._validation import (
    optional_str_field,
    optional_uuid_field,
    parse_json_body,
    require_str_field,
)


def _fake_request(payload):
    """Mini-stub con solo el atributo `.body` necesario para parse_json_body."""
    body = (
        payload
        if isinstance(payload, (bytes, bytearray))
        else json.dumps(payload).encode()
    )
    return SimpleNamespace(body=body)


class TestParseJsonBody:
    def test_returns_dict_when_valid(self):
        # Arrange
        request = _fake_request({"foo": "bar"})

        # Act
        body, err = parse_json_body(request)

        # Assert
        assert err is None
        assert body == {"foo": "bar"}

    def test_returns_400_when_json_invalid(self):
        # Arrange
        request = SimpleNamespace(body=b"{not valid json")

        # Act
        body, err = parse_json_body(request)

        # Assert
        assert body is None
        assert err is not None
        assert err.status_code == 400

    def test_returns_400_when_body_is_list(self):
        # Arrange
        request = _fake_request([1, 2, 3])

        # Act
        body, err = parse_json_body(request)

        # Assert
        assert body is None
        assert err is not None
        assert err.status_code == 400

    def test_returns_400_when_body_is_scalar(self):
        # Arrange
        request = _fake_request("hello")

        # Act
        body, err = parse_json_body(request)

        # Assert
        assert body is None
        assert err is not None
        assert err.status_code == 400


class TestRequireStrField:
    def test_returns_stripped_value(self):
        # Arrange
        body = {"name": "  hola  "}

        # Act
        value, err = require_str_field(body, "name")

        # Assert
        assert err is None
        assert value == "hola"

    def test_returns_400_when_missing(self):
        # Arrange
        body = {}

        # Act
        value, err = require_str_field(body, "name")

        # Assert
        assert value is None
        assert err is not None
        assert err.status_code == 400

    def test_returns_400_when_not_string(self):
        # Arrange
        body = {"name": 123}

        # Act
        value, err = require_str_field(body, "name")

        # Assert
        assert value is None
        assert err is not None
        assert err.status_code == 400

    def test_returns_400_when_only_whitespace(self):
        # Arrange
        body = {"name": "   "}

        # Act
        value, err = require_str_field(body, "name")

        # Assert
        assert value is None
        assert err is not None
        assert err.status_code == 400

    def test_returns_400_when_exceeds_max_length(self):
        # Arrange
        body = {"name": "a" * 11}

        # Act
        value, err = require_str_field(body, "name", max_length=10)

        # Assert
        assert value is None
        assert err is not None
        assert err.status_code == 400


class TestOptionalStrField:
    def test_returns_none_when_missing(self):
        # Arrange
        body = {}

        # Act
        value, err = optional_str_field(body, "name")

        # Assert
        assert value is None
        assert err is None

    def test_returns_none_when_explicit_null(self):
        # Arrange
        body = {"name": None}

        # Act
        value, err = optional_str_field(body, "name")

        # Assert
        assert value is None
        assert err is None

    def test_returns_400_when_not_string(self):
        # Arrange
        body = {"name": 42}

        # Act
        value, err = optional_str_field(body, "name")

        # Assert
        assert value is None
        assert err is not None
        assert err.status_code == 400


class TestOptionalUuidField:
    def test_returns_uuid_when_valid(self):
        # Arrange
        u = uuid4()
        body = {"id": str(u)}

        # Act
        value, err = optional_uuid_field(body, "id")

        # Assert
        assert err is None
        assert value == u

    def test_returns_none_when_missing(self):
        # Arrange
        body = {}

        # Act
        value, err = optional_uuid_field(body, "id")

        # Assert
        assert value is None
        assert err is None

    def test_returns_400_when_invalid(self):
        # Arrange
        body = {"id": "not-a-uuid"}

        # Act
        value, err = optional_uuid_field(body, "id")

        # Assert
        assert value is None
        assert err is not None
        assert err.status_code == 400
