import unittest

import app


class ServiceRoutingTests(unittest.TestCase):

    def test_specific_service_requests_use_catalogue(self):
        cases = {
            "I want a birth certificate": "Birth Certificate",
            "I want income tax": "Income Tax",
            "I want a driving licence": "Driving Licence",
            "I need Aadhaar": "Aadhaar",
            "I want a passport": "Passport",
        }

        for request, expected in cases.items():
            with self.subTest(request=request):
                service = app.find_registry_service(request)
                self.assertIsNotNone(service)
                self.assertEqual(
                    service["service_name"],
                    expected,
                )

    def test_ambiguous_certificate_request_does_not_guess(self):
        self.assertIsNone(
            app.find_registry_service(
                "I need a certificate"
            )
        )
        self.assertTrue(
            app.is_ambiguous_request(
                "I need a certificate"
            )
        )

    def test_greeting_is_not_routed_to_a_service(self):
        self.assertTrue(app.is_general_message("Hello"))
        self.assertIsNone(
            app.resolve_service_request("Hello")
        )

    def test_catalogue_search_returns_relevant_services(self):
        tax_matches = app.search_registry_services("tax")
        self.assertEqual(
            tax_matches[0]["service_name"],
            "Income Tax",
        )

        licence_matches = app.search_registry_services(
            "licence"
        )
        self.assertEqual(
            licence_matches[0]["service_name"],
            "Driving Licence",
        )


if __name__ == "__main__":
    unittest.main()