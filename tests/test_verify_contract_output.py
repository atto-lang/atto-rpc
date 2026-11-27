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


    def test_json_nonfinite_tokens_and_nonstring_required_fail_closed(self):
        bad = self.file('{"$schema":"https://json-schema.org/draft/2020-12/schema",'
                        '"$id":"https://example.test/rpc","$defs":{},"unknown":NaN}', 'nan.json')
        with self.assertRaisesRegex(verification.ContractError, "nonstandard JSON"):
            verification.validate_json_schema(bad)
        doc = json.loads(self.schema().read_text())
        doc["$defs"]["Request"]["required"] = [[]]
        with self.assertRaisesRegex(verification.ContractError, "invalid required"):
            verification.validate_json_schema(self.schema(doc))

    def test_cross_idl_positive_and_type_drift(self):
        schema = verification.validate_json_schema(self.schema())
        self.assertTrue(verification.validate_cross_idl(schema, self.mpack()))
        changed = self.mpack().read_text().replace("1 id: str", "1 id: int")
        with self.assertRaisesRegex(verification.ContractError, "type mismatch"):
            verification.validate_cross_idl(schema, self.mpack(changed))

    def test_cross_idl_message_and_field_drift(self):
        schema = verification.validate_json_schema(self.schema())
        mismatch = "mpackdef 1\nencoding map-int-keys\nmessage Missing {\n}\n"
        with self.assertRaisesRegex(verification.ContractError, "message registry mismatch"):
            verification.validate_cross_idl(schema, self.mpack(mismatch))
        missing_field = "mpackdef 1\nencoding map-int-keys\nmessage Request {\n}\n"
        with self.assertRaisesRegex(verification.ContractError, "fields mismatch"):
            verification.validate_cross_idl(schema, self.mpack(missing_field))

    def test_cross_idl_requiredness_and_dangling_rpc(self):
        schema = verification.validate_json_schema(self.schema())
        source = self.mpack().read_text()
        with self.assertRaisesRegex(verification.ContractError, "requiredness mismatch"):
            verification.validate_cross_idl(schema, self.mpack(source.replace("str required", "str optional")))
        with self.assertRaisesRegex(verification.ContractError, "unknown message"):
            verification.validate_cross_idl(schema, self.mpack(source.replace("-> Request", "-> Missing")))

    def test_cross_idl_resolves_recursive_named_message(self):
        doc = json.loads(self.schema().read_text())
        doc["$defs"]["Request"]["properties"]["id"] = {"$ref": "#/$defs/Request"}
        schema = verification.validate_json_schema(self.schema(doc))
        named = "mpackdef 1\nencoding map-int-keys\nmessage Request {\n  1 id: Request required\n}\n"
        self.assertTrue(verification.validate_cross_idl(schema, self.mpack(named)))
        with self.assertRaisesRegex(verification.ContractError, "unresolved MessagePack field type"):
            verification.validate_cross_idl(schema, self.mpack(named.replace("Request required", "Unknown required")))

    def test_input_size_empty_and_symlink_are_rejected(self):
        small = self.file("abc", "small")
        verification.require_bounded_artifacts((small,), max_bytes=3)
        with self.assertRaisesRegex(verification.ContractError, "size"):
            verification.require_bounded_artifacts((small,), max_bytes=2)
        empty = self.file("", "empty")
        with self.assertRaisesRegex(verification.ContractError, "size"):
            verification.require_bounded_artifacts((empty,))
        link = self.root / "symlink"
        link.symlink_to(small)
        with self.assertRaisesRegex(verification.ContractError, "symlink"):
            verification.require_bounded_artifacts((link,))

    def test_external_compiler_timeout_is_not_success(self):
        from subprocess import TimeoutExpired
        with patch.object(verification.shutil, "which", side_effect=lambda name: name), \
             patch.object(verification.subprocess, "run",
                          side_effect=TimeoutExpired(["protoc"], timeout=90)):
            with self.assertRaises(TimeoutExpired):
                verification.validate_external(self.root / "a.proto", self.root / "a.tsp")

    def test_fail_closed_missing_external_tools(self):
        with patch.object(verification.shutil, 'which', return_value=None):
            with self.assertRaisesRegex(verification.ContractError, "'protoc' not installed"):
                verification.validate_external(self.root/'contract.proto', self.root/'contract.tsp')


if __name__ == '__main__':
    unittest.main()
