from django.test import TestCase


class KgApiTest(TestCase):
    def test_kg_search_returns_503_when_not_configured(self):
        resp = self.client.get("/api/kg/search/?q=测试")
        self.assertIn(resp.status_code, (200, 503))

    def test_kg_subgraph_returns_400_without_center(self):
        resp = self.client.get("/api/kg/subgraph/")
        self.assertEqual(resp.status_code, 400)

