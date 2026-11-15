
import json
from decimal import Decimal
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest

from app.routing import (
    RouteResult,
    RoutingError,
    get_driving_route,
)


BASE_ARGS = {
    "base_url": "http://localhost:5000",
    "pickup_latitude": 55.123,
    "pickup_longitude": 37.456,
    "destination_latitude": 55.130,
    "destination_longitude": 37.470,
    "timeout_seconds": 8.0,
}


def make_response(payload):
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode("utf-8")
    return response


def test_successful_route():
    payload = {
        "code": "Ok",
        "routes": [
            {
                "distance": 2500.5,
                "duration": 600.25,
            }
        ],
    }

    with patch(
        "app.routing.urlopen",
        return_value=make_response(payload),
    ):
        result = get_driving_route(**BASE_ARGS)

    assert result == RouteResult(
        distance_meters=Decimal("2500.5"),
        duration_seconds=Decimal("600.25"),
    )
    assert result.distance_km == Decimal("2.5005")
    assert result.duration_minutes == Decimal("600.25") / Decimal("60")


def test_connection_error():
    with patch(
        "app.routing.urlopen",
        side_effect=URLError("Connection refused"),
    ):
        with pytest.raises(RoutingError):
            get_driving_route(**BASE_ARGS)


def test_timeout_error():
    with patch(
        "app.routing.urlopen",
        side_effect=TimeoutError("Request timed out"),
    ):
        with pytest.raises(RoutingError):
            get_driving_route(**BASE_ARGS)


def test_invalid_json():
    response = MagicMock()
    response.read.return_value = b"not-json"

    with patch("app.routing.urlopen", return_value=response):
        with pytest.raises(RoutingError):
            get_driving_route(**BASE_ARGS)


def test_empty_routes():
    payload = {
        "code": "Ok",
        "routes": [],
    }

    with patch(
        "app.routing.urlopen",
        return_value=make_response(payload),
    ):
        with pytest.raises(RoutingError):
            get_driving_route(**BASE_ARGS)


def test_zero_distance_is_rejected():
    payload = {
        "code": "Ok",
        "routes": [
            {
                "distance": 0,
                "duration": 600,
            }
        ],
    }

    with patch(
        "app.routing.urlopen",
        return_value=make_response(payload),
    ):
        with pytest.raises(RoutingError):
            get_driving_route(**BASE_ARGS)


def test_zero_duration_is_rejected():
    payload = {
        "code": "Ok",
        "routes": [
            {
                "distance": 2500,
                "duration": 0,
            }
        ],
    }

    with patch(
        "app.routing.urlopen",
        return_value=make_response(payload),
    ):
        with pytest.raises(RoutingError):
            get_driving_route(**BASE_ARGS)


@pytest.mark.parametrize(
    "field,value",
    [
        ("pickup_latitude", 91),
        ("pickup_longitude", 181),
        ("destination_latitude", -91),
        ("destination_longitude", -181),
    ],
)
def test_invalid_coordinates(field, value):
    args = dict(BASE_ARGS)
    args[field] = value

    with pytest.raises(ValueError):
        get_driving_route(**args)


def test_invalid_route_structure():
    payload = {
        "code": "Ok",
        "routes": ["invalid"],
    }

    with patch(
        "app.routing.urlopen",
        return_value=make_response(payload),
    ):
        with pytest.raises(RoutingError):
            get_driving_route(**BASE_ARGS)
