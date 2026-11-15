import unittest
from reference.rpc_envelope import EnvelopeError, decode_envelope, encode_envelope


class EnvelopeContractTest(unittest.TestCase):
    def test_request_and_response_round_trip(self):
        messages = [
            {"v": 1, "kind": "request", "id": 7, "method": "get_user",
             "params": {"user_id": 13}},
            {"v": 1, "kind": "notification", "method": "ping", "params": []},
            {"v": 1, "kind": "response", "id": 7, "result": {"ok": True}},
            {"v": 1, "kind": "error", "id": 7,
             "error": {"code": "not_found", "message": "missing"}},
        ]
        for message in messages:
            with self.subTest(kind=message["kind"]):
                self.assertEqual(decode_envelope(encode_envelope(message)), message)

    def test_rejects_duplicate_and_nonfinite_json(self):
        for blob in [b'{"v":1,"v":1}', b'{"v":1,"kind":"response","id":1,"result":NaN}']:
            with self.assertRaises(EnvelopeError):
                decode_envelope(blob)

    def test_invalid_fields_and_ids(self):
        base = {"v": 1, "kind": "request", "id": 1,
                "method": "get_user", "params": []}
        for change in [{"id": True}, {"id": -1}, {"id": 1 << 53},
                       {"method": "GetUser"}, {"method": "x-y"},
                       {"params": 7}, {"secret": "unknown"}, {"v": True}]:
            with self.subTest(change=change), self.assertRaises(EnvelopeError):
                encode_envelope(dict(base, **change))

    def test_invalid_json_and_size_limits(self):
        for blob in [b'\xff', b'[]', b' ' * 65537]:
            with self.assertRaises(EnvelopeError):
                decode_envelope(blob)
        with self.assertRaises(EnvelopeError):
            encode_envelope({"v": 1, "kind": "response", "id": 0,
                             "result": "x" * 65536})


if __name__ == "__main__":
    unittest.main()
