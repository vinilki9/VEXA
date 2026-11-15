
import unittest

from app.routing import RoutingError
from app.routing_providers import (
    OSRMProvider,
    TwoGISProvider,
    YandexProvider,
    get_routing_provider,
)


class RoutingProviderTests(unittest.TestCase):

    def test_selects_osrm_provider(self):
        provider = get_routing_provider(
            provider_name=" OSRM ",
            osrm_base_url=" http://localhost:5000/ ",
            timeout_seconds=8.0,
        )

        self.assertIsInstance(provider, OSRMProvider)
        self.assertEqual(
            provider.base_url,
            "http://localhost:5000",
        )
        self.assertEqual(provider.timeout_seconds, 8.0)

    def test_selects_two_gis_provider(self):
        provider = get_routing_provider(
            provider_name="2gis",
            osrm_base_url="",
            two_gis_api_key=" test-key ",
            timeout_seconds=8.0,
        )

        self.assertIsInstance(provider, TwoGISProvider)
        self.assertEqual(provider.api_key, "test-key")

    def test_selects_yandex_provider(self):
        provider = get_routing_provider(
            provider_name="yandex",
            osrm_base_url="",
            yandex_api_key=" test-key ",
            timeout_seconds=8.0,
        )

        self.assertIsInstance(provider, YandexProvider)
        self.assertEqual(provider.api_key, "test-key")

    def test_unknown_provider_is_rejected(self):
        with self.assertRaises(RoutingError):
            get_routing_provider(
                provider_name="unknown",
                osrm_base_url="",
            )

    def test_empty_osrm_url_is_rejected(self):
        with self.assertRaises(RoutingError):
            get_routing_provider(
                provider_name="osrm",
                osrm_base_url="   ",
            )

    def test_invalid_timeout_is_rejected(self):
        invalid_timeouts = [
            0,
            -1,
            30.1,
            float("inf"),
            float("nan"),
        ]

        for timeout in invalid_timeouts:
            with self.subTest(timeout=timeout):
                with self.assertRaises(ValueError):
                    get_routing_provider(
                        provider_name="osrm",
                        osrm_base_url="http://localhost:5000",
                        timeout_seconds=timeout,
                    )

    def test_two_gis_rejects_invalid_timeout(self):
        with self.assertRaises(ValueError):
            get_routing_provider(
                provider_name="2gis",
                osrm_base_url="",
                two_gis_api_key="test-key",
                timeout_seconds=0,
            )

    def test_yandex_rejects_invalid_timeout(self):
        with self.assertRaises(ValueError):
            get_routing_provider(
                provider_name="yandex",
                osrm_base_url="",
                yandex_api_key="test-key",
                timeout_seconds=31,
            )

    def test_two_gis_rejects_empty_api_key(self):
        provider = get_routing_provider(
            provider_name="2gis",
            osrm_base_url="",
            two_gis_api_key="   ",
        )

        with self.assertRaises(RoutingError):
            provider.get_route(55.1, 37.2, 55.2, 37.3)

    def test_yandex_rejects_empty_api_key(self):
        provider = get_routing_provider(
            provider_name="yandex",
            osrm_base_url="",
            yandex_api_key="   ",
        )

        with self.assertRaises(RoutingError):
            provider.get_route(55.1, 37.2, 55.2, 37.3)


if __name__ == "__main__":
    unittest.main()
