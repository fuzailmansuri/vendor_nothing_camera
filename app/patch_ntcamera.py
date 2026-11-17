#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Paranoid Android
# SPDX-License-Identifier: Apache-2.0

import argparse
import hashlib
import os
from pathlib import Path
import struct
import zipfile
import zlib


# shortcut: pinned C5.0 bytecode, refresh this patch when the camera APK changes.
DEX_SHA256 = "4f4ef741ef88751b9eadc56cffbab1b0b772d8903d9b3d87931c5e9cd6e98310"
PATCHED_DEX_SHA256 = "0c7429603a2f336e30e9ad766a6f9c5b8389a4913c2973772bd2395f520d131b"
PATCH_OFFSET = 5734104
ORIGINAL = bytes.fromhex("7120a86427000c07")
# ProductConfig.<clinit>: use the existing "Asteroids" string instead of ro.product.device.
REPLACEMENT = bytes.fromhex("1a07971b00000000")
# FeatureConfigParser.initPropertyValue: keep ConfigMapAsteroids[Plus] selection.
FEATURE_OFFSET = 5690478
FEATURE_ORIGINAL = bytes.fromhex("7120a86432000c02")
FEATURE_REPLACEMENT = bytes.fromhex("1a02971b00000000")
# C5.0 omits the engine; its dehaze wrapper differs from our previous APK only by build ID.
DEHAZE_SHA256 = "f26695afd804a162932796b709f153e870d9e9fafc454b3f456bf960ff80e086"
DEHAZE_MEMBER = "lib/arm64-v8a/libarcsoft_dehaze.so"


def patch_dex(data):
    digest = hashlib.sha256(data).hexdigest()
    if digest == PATCHED_DEX_SHA256:
        return data
    if (digest != DEX_SHA256
            or data[PATCH_OFFSET:PATCH_OFFSET + 8] != ORIGINAL
            or data[FEATURE_OFFSET:FEATURE_OFFSET + 8] != FEATURE_ORIGINAL):
        raise ValueError("NTCamera bytecode changed; refresh the Asteroids device patch")

    patched = bytearray(data)
    patched[PATCH_OFFSET:PATCH_OFFSET + 8] = REPLACEMENT
    patched[FEATURE_OFFSET:FEATURE_OFFSET + 8] = FEATURE_REPLACEMENT
    patched[12:32] = hashlib.sha1(patched[32:]).digest()
    struct.pack_into("<I", patched, 8, zlib.adler32(patched[12:]) & 0xffffffff)
    if hashlib.sha256(patched).hexdigest() != PATCHED_DEX_SHA256:
        raise ValueError("NTCamera device patch produced unexpected bytecode")
    return bytes(patched)


def resolve_source(source):
    src = Path(source)
    if src.exists():
        return src
    if src.is_symlink():
        target = os.readlink(source)
        for anchor in [Path.cwd(), Path(__file__).resolve()]:
            anchor_str = str(anchor)
            if "/out/" in anchor_str:
                root = Path(anchor_str.split("/out/")[0])
                candidate = (root / src.parent / target).resolve()
                if candidate.exists():
                    return candidate
    return src


def patch_apk(source, output, dehaze_library):
    source = resolve_source(source)
    if Path(output).resolve() in (Path(source).resolve(), Path(dehaze_library).resolve()):
        raise ValueError("Camera inputs must remain unchanged")
    engine = Path(dehaze_library).read_bytes()
    if hashlib.sha256(engine).hexdigest() != DEHAZE_SHA256:
        raise ValueError("Unexpected dehaze engine; review its camera compatibility")
    with zipfile.ZipFile(source) as original:
        dex = patch_dex(original.read("classes5.dex"))
        has_engine = DEHAZE_MEMBER in original.namelist()
        if has_engine and original.read(DEHAZE_MEMBER) != engine:
            raise ValueError("NTCamera already contains a different dehaze engine")
        with zipfile.ZipFile(output, "w") as patched:
            patched.comment = original.comment
            for member in original.infolist():
                name = member.filename
                # android_app_import signs the generated APK with the platform certificate.
                if name.startswith("META-INF/") and (
                    name == "META-INF/MANIFEST.MF"
                    or name.endswith((".SF", ".RSA", ".DSA", ".EC"))
                ):
                    continue
                patched.writestr(member, dex if name == "classes5.dex" else original.read(name))
            if not has_engine:
                # Match the stock wrapper's ZIP packaging; android_app_import aligns/signs it.
                member = original.getinfo("lib/arm64-v8a/libdehaze.so")
                added = zipfile.ZipInfo(DEHAZE_MEMBER, member.date_time)
                added.compress_type = member.compress_type
                added.external_attr = member.external_attr
                patched.writestr(added, engine)


def main():
    parser = argparse.ArgumentParser(description="Keep NTCamera on the Asteroids product profile")
    parser.add_argument("source")
    parser.add_argument("output")
    parser.add_argument("dehaze_library")
    args = parser.parse_args()
    patch_apk(args.source, args.output, args.dehaze_library)


if __name__ == "__main__":
    main()
