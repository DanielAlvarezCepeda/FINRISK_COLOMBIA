import unittest
from fastapi.testclient import TestClient
from api.main import app, INFO, METRICS

EXAMPLE = {'liquidez_corriente': 1.2, 'endeudamiento': .6, 'roa': .03, 'margen_neto': .05}

class TestAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = TestClient(app)
        cls.client = cls.context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None, None, None)

    def test_health(self):
        r = self.client.get('/health')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['sha256_modelo'], INFO['sha256_modelo'])

    def test_info_and_metrics(self):
        self.assertEqual(self.client.get('/model/info').json(), INFO)
        self.assertEqual(self.client.get('/metrics').json(), METRICS)

    def test_prediction_matches_pipeline(self):
        from api.main import score
        expected = score(app.state.pipeline, EXAMPLE)
        r = self.client.post('/predict', json=EXAMPLE)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertAlmostEqual(data['puntaje'], expected, places=12)
        self.assertEqual(data['alerta'], expected >= INFO['umbral'])
        self.assertFalse(data['puntaje_calibrado'])

    def test_negative_profit(self):
        r = self.client.post('/predict', json={**EXAMPLE, 'roa': -.12, 'margen_neto': -.1})
        self.assertEqual(r.status_code, 200)

    def test_invalid_missing_or_extra(self):
        for bad in ({}, {**EXAMPLE, 'nit': '900000000'}, {**EXAMPLE, 'roa': None}, {**EXAMPLE, 'roa': '0.3'}, {**EXAMPLE, 'roa': 1e31}):
            self.assertEqual(self.client.post('/predict', json=bad).status_code, 422)

if __name__ == '__main__':
    unittest.main()
