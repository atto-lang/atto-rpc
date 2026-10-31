"""Host-only export contracts; fake compiler does not constitute guest proof."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXPORT_NAMES = ('json_schema', 'protobuf', 'messagepack', 'typespec')
FILENAMES = ('contracts.schema.json', 'contracts.proto', 'contracts.mpackdef', 'contracts.tsp')


class ExportContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.project = self.work / 'project with spaces'
        for name in ('scripts', 'tests'):
            (self.project / name).mkdir(parents=True)
        for script in ('test.sh', 'export-contracts.sh', 'emit-guest-document.py', 'bounded_process.py'):
            shutil.copyfile(ROOT / 'scripts' / script, self.project / 'scripts' / script)
        (self.project / 'tests' / 'expected.txt').write_bytes(b'test-output\n')
        (self.project / 'tests' / 'rpc_semantics.ores').write_text('native fixture\n')
        for entry in EXPORT_NAMES:
            shutil.copyfile(ROOT / 'tests' / f'export_{entry}.ores', self.project / 'tests' / f'export_{entry}.ores')
        source = self.work / 'compiler source'
        source.mkdir()
        subprocess.run(['git', '-C', str(source), 'init', '-q'], check=True)
        (source / 'tracked').write_text('compiler\n')
        subprocess.run(['git', '-C', str(source), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(source), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture'], check=True)
        revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
        (self.project / 'SOURCE_REF').write_text(revision + '\n')
        self.compiler = self.work / 'fake-compiler'
        self.compiler.write_text('''#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" = --check ]]; then
  test "$2" = --platform=server
  test -f "$3"
  exit 0
fi
test "$1" = --platform=server
test -f "$2"
case "${2##*/}" in
  rpc_semantics.ores) printf 'test-output\\n' ;;
  export_*.ores)
    if [[ "${FAIL_EXPORT:-}" == "${2##*/}" ]]; then exit 41; fi
    if [[ "${FLOOD_EXPORT:-}" == "${2##*/}" ]]; then head -c 1048577 /dev/zero; exit 0; fi
    if [[ "${FLOOD_STDERR:-}" == "${2##*/}" ]]; then head -c 1048577 /dev/zero >&2; exit 0; fi
    if [[ "${SLOW_EXPORT:-}" == "${2##*/}" ]]; then sleep 3; fi
    if [[ "${INVALID_UTF8:-}" == "${2##*/}" ]]; then printf '\\377'; exit 0; fi
    printf 'fragment\\n\\nexact<%s>' "${2##*/}" ;;
  *) exit 90 ;;
esac
''')
        self.compiler.chmod(0o755)
        self.env = dict(os.environ, ORESLANG_SOURCE_DIR=str(source), ORESLANG_COMPILER=str(self.compiler))
        self.dest = self.work / 'output files'

    def run_export(self, *, env=None):
        return subprocess.run(['bash', str(self.project / 'scripts' / 'export-contracts.sh'), str(self.dest)], env=env or self.env, cwd=self.work, capture_output=True, text=True)

    def test_exact_bytes_without_extra_newline(self):
        proc = self.run_export()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for name, entry in zip(FILENAMES, EXPORT_NAMES):
            self.assertEqual((self.dest / name).read_bytes(), b'fragment\n\nexact<export_' + entry.encode() + b'.ores>')
        self.assertEqual(sorted(x.name for x in self.dest.iterdir()), sorted(FILENAMES))

    def test_fail_closed_and_no_partial_published_directory(self):
        for case in (EXPORT_NAMES[0], EXPORT_NAMES[-1]):
            with self.subTest(case=case):
                env = dict(self.env, FAIL_EXPORT=f'export_{case}.ores')
                result = self.run_export(env=env)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.dest.exists())
                self.assertFalse(list(self.work.glob('.rpc-export.*')))

    def test_oversized_artifact_rejected_without_partial_publish(self):
        env = dict(self.env, FLOOD_EXPORT='export_typespec.ores')
        result = self.run_export(env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('compiler output budget exceeded', result.stderr)
        self.assertFalse(self.dest.exists())
        self.assertFalse(list(self.work.glob('.rpc-export.*')))

    def test_stderr_flood_cannot_bypass_combined_budget(self):
        env = dict(self.env, FLOOD_STDERR='export_typespec.ores')
        result = self.run_export(env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('compiler output budget exceeded', result.stderr)
        self.assertFalse(self.dest.exists())

    def test_hanging_export_times_out_without_publication(self):
        env = dict(self.env, SLOW_EXPORT='export_typespec.ores',
                   ORESLANG_RPC_EXPORT_TIMEOUT_SECONDS='0.1')
        result = self.run_export(env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('timed out', result.stderr)
        self.assertFalse(self.dest.exists())
        self.assertFalse(list(self.work.glob('.rpc-export.*')))

    def test_invalid_utf8_rejected_before_publication(self):
        env = dict(self.env, INVALID_UTF8='export_typespec.ores')
        result = self.run_export(env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('utf-8', result.stderr)
        self.assertFalse(self.dest.exists())

    def test_four_export_entrypoints_share_identical_contract_graph(self):
        expected = None
        for entry in EXPORT_NAMES:
            code = (ROOT / 'tests' / f'export_{entry}.ores').read_text()
            self.assertIn(f'generated.{entry}', code)
            code = code.replace(f'generated.{entry}', 'generated.FORMAT')
            if expected is None:
                expected = code
            else:
                self.assertEqual(expected, code)

    def test_existing_destination_rejected_without_changes(self):
        self.dest.mkdir()
        marker = self.dest / 'untouched'
        marker.write_text('sentinel')
        self.assertNotEqual(self.run_export().returncode, 0)
        self.assertEqual(marker.read_text(), 'sentinel')

    def test_dirty_compiler_rejected(self):
        (Path(self.env['ORESLANG_SOURCE_DIR']) / 'tracked').write_text('dirty')
        result = self.run_export()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.dest.exists())
        self.assertIn('must be clean', result.stderr)

    def test_missing_compiler_rejected(self):
        env = dict(self.env, ORESLANG_COMPILER=str(self.work / 'not-found'))
        result = self.run_export(env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.dest.exists())


if __name__ == '__main__':
    unittest.main()
