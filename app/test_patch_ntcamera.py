#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import hashlib
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile
import zlib

import patch_ntcamera as patch


class CameraProfilePatchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.apk = Path(__file__).resolve().parents[1] / "proprietary/system_ext/priv-app/NTCamera/NTCamera.apk"
        cls.engine = Path(__file__).with_name("libarcsoft_dehaze.so")
        with zipfile.ZipFile(cls.apk) as archive:
            cls.dex = archive.read("classes5.dex")

    def test_only_profile_readers_and_dex_checksums_change(self):
        result = patch.patch_dex(self.dex)
        allowed = set(range(8, 32))
        allowed.update(range(patch.PATCH_OFFSET, patch.PATCH_OFFSET + 8))
        allowed.update(range(patch.FEATURE_OFFSET, patch.FEATURE_OFFSET + 8))
        changed = {i for i, (old, new) in enumerate(zip(self.dex, result)) if old != new}
        self.assertTrue(changed)
        self.assertTrue(changed <= allowed)
        self.assertEqual(len(self.dex), len(result))
        self.assertEqual(result[12:32], hashlib.sha1(result[32:]).digest())
        self.assertEqual(struct.unpack_from("<I", result, 8)[0], zlib.adler32(result[12:]) & 0xffffffff)
        self.assertEqual(patch.patch_dex(result), result)

    def test_changed_or_truncated_bytecode_is_rejected(self):
        changed = bytearray(self.dex)
        changed[-1] ^= 1
        for invalid in (changed, self.dex[:-1], b""):
            with self.assertRaises(ValueError):
                patch.patch_dex(invalid)

    def test_apk_preserves_other_dex_native_resources_and_manifest(self):
        digest = hashlib.sha256(self.apk.read_bytes()).digest()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "camera.apk"
            patch.patch_apk(self.apk, output, self.engine)
            with zipfile.ZipFile(self.apk) as source, zipfile.ZipFile(output) as result:
                self.assertEqual(len([n for n in result.namelist() if n.endswith(".dex")]), 8)
                for name in result.namelist():
                    if name == "classes5.dex":
                        continue
                    if name == patch.DEHAZE_MEMBER:
                        self.assertEqual(result.read(name), self.engine.read_bytes())
                        continue
                    self.assertEqual(result.read(name), source.read(name), name)
                self.assertEqual(result.read(patch.DEHAZE_MEMBER), self.engine.read_bytes())
            patch.patch_apk(output, Path(directory) / "repeated.apk", self.engine)
            with zipfile.ZipFile(Path(directory) / "repeated.apk") as repeated:
                self.assertEqual(repeated.namelist().count(patch.DEHAZE_MEMBER), 1)
        self.assertEqual(hashlib.sha256(self.apk.read_bytes()).digest(), digest)

    def test_source_cannot_be_overwritten(self):
        with self.assertRaises(ValueError):
            patch.patch_apk(self.apk, self.apk, self.engine)
        with self.assertRaises(ValueError):
            patch.patch_apk(self.apk, self.engine, self.engine)

    def test_unknown_dehaze_engine_is_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "engine.so"
            invalid.write_bytes(b"invalid")
            output = Path(directory) / "camera.apk"
            with self.assertRaises(ValueError):
                patch.patch_apk(self.apk, output, invalid)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
