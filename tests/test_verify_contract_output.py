import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/verify-contract-output.py'
spec = importlib.util.spec_from_file_location('verification', SCRIPT)
verification = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verification)


class ContractOutputVerification(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def file(self, contents, name):
        path = self.root / name
        path.write_text(contents, encoding='utf-8')
        return path

    def schema(self, value=None):
        if value is None:
            value = {
                '$schema': 'https://json-schema.org/draft/2020-12/schema',
                '$id': 'https://example.test/rpc',
                '$defs': {'Request': {'type': 'object', 'additionalProperties': False,
                                      'properties': {'id': {'type': 'string'}}, 'required': ['id']}}
            }
        return self.file(json.dumps(value), 'contract.schema.json')

    def mpack(self, text=None):
        if text is None:
            text = 'mpackdef 1\nencoding map-int-keys\n\nmessage Request {\n  1 id: str required\n}\n\nrpc Users.Get(Request) -> Request\n'
        return self.file(text, 'contract.mpackdef')

    def test_valid_json_schema_and_msgpack(self):
        self.assertIn('$defs', verification.validate_json_schema(self.schema()))
        self.assertEqual((1, 1), verification.validate_msgpack_def(self.mpack()))

    def test_json_duplicates_and_invalid_required(self):
        duplicate = self.file('{"$schema":"https://json-schema.org/draft/2020-12/schema","$defs":{},"$defs":{}}', 'bad.json')
        with self.assertRaisesRegex(verification.ContractError, 'duplicate'):
            verification.validate_json_schema(duplicate)
        data = json.loads(self.schema().read_text())
        data['$defs']['Request']['required'] = ['missing']
        with self.assertRaisesRegex(verification.ContractError, 'required'):
            verification.validate_json_schema(self.schema(data))

    def test_msgpack_field_number_and_name_collision(self):
        base = 'mpackdef 1\nencoding map-int-keys\nmessage Request {\n  1 id: str required\n  {}\n}\n'
        for malformed in ['1 other: str optional', '2 id: str optional', '01 other: str optional',
                          '19000 other: str optional', '536870912 other: str optional',
                          '2 evil: str required; injected']:
            with self.subTest(malformed=malformed), self.assertRaises(verification.ContractError):
                verification.validate_msgpack_def(self.mpack(base.replace('{}', malformed)))

    def test_msgpack_repeated_required_and_unterminated(self):
        base = 'mpackdef 1\nencoding map-int-keys\nmessage Request {\n  1 id: array<str> required\n}\n'
        with self.assertRaisesRegex(verification.ContractError, r'required\+repeated'):
            verification.validate_msgpack_def(self.mpack(base))
        with self.assertRaisesRegex(verification.ContractError, 'unterminated'):
            verification.validate_msgpack_def(self.mpack('mpackdef 1\nencoding map-int-keys\nmessage Request {\n'))

    def test_fail_closed_missing_external_tools(self):
        with patch.object(verification.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(verification.ContractError, "'protoc' not installed"):
                verification.validate_external(self.root/'contract.proto', self.root/'contract.tsp')


if __name__ == '__main__':
    unittest.main()
