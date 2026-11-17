# Nothing Camera for Nothing Phone (3a)

Nothing Camera (`com.nothing.camera`) for the Nothing Phone (3a) / (3a) Pro
(asteroids), as a drop-in extract-utils vendor repository.
Clone to `vendor/nothing/camera` and run `git lfs pull`.

The current drop uses Nothing OS `Asteroids_C5.0-261106-1007`, including
NTCamera **17.0.00.78.04** (version code `170007804`). The APK targets SDK 36.

## Integration

```make
# BoardConfig.mk
-include vendor/nothing/camera/BoardConfigCamera.mk

# device.mk
$(call inherit-product-if-exists, vendor/nothing/camera/nothing-camera.mk)
```

Both are optional includes, so the device still builds without this repo
(Aperture keeps working, Nothing Camera is simply absent).

## Requirements

This repo is not enough on its own. The build also needs:

- Android 17: the sepolicy uses `platform_app_36`, the domain platform signed
  apps targeting SDK 36 run in. It does not exist on older releases.
- A `libui_shim` module in the tree, linked by
  `vendor.noth.hardware.camera-service-impl.so`.
- `nothing-fwk` in the device tree with `com.nothing.NtFeaturesUtils`
  exposing the feature ids the app reads by reflection
  (`NTF_QCOM = 59`, `NTF_MTK = 60`, `NTF_PONG = 62`, `NTF_PACMAN = 63`,
  `NTF_TETRIS = 64`, `NTF_ASTEROIDS = 80`, `NTF_ASTEROIDS_PLUS = 86`,
  `NTF_IND = 88`, `NTF_JPN = 89`, `NTF_DRAGONITE = 110`,
  `NTF_BACKGROUND_RES_LIMIT = 115`, `NTF_LINEAR_VIBRATOR = 139`),
  and falling back to `ro.vendor.nothing.feature.diff.{device,plus}.Asteroids`
  when no prop exists for `Build.DEVICE`.
- The Nothing feature props, readable by `platform_app` and
  `platform_app_36` (`get_prop(..., vendor_nothing_feature_prop)`):

  ```
  ro.vendor.nothing.feature.base=0x1004458438124a040126b4247b97ffL
  ro.vendor.nothing.feature.diff.device.Asteroids=0xa80c901acc038d140ad44002d8842080L
  ro.vendor.nothing.feature.diff.plus.Asteroids=0x4000000000000000000000L
  ```

  These are the port's ODM-owned masks. Keep their device/SKU selection when
  updating; importing every stock feature bit can select Nothing OS features
  that the ROM does not implement.
- Nothing's common sepolicy, for the `vendor_ntf_file` type and
  `com.nothing.camera.postproc.IPostProcService/default` labelled
  `vendor_hal_camera_service`.
- `hal_camera_default` with its stock QTI permissions (DSP,
  `vendor_camera_prop`, postproc hwservice). No changes to the QTI vendor
  sepolicy are needed.
- The device's vendor tree (`vendor/nothing/asteroids`, imported by this
  repo's soong namespace for `libntcamcore` and friends), extracted with the
  rules below.

The device tree also needs the extract rules listed under
[Device-tree side](#device-tree-side-not-in-this-repo), all of which patch stock
blobs that belong to the device.

## Contents

| Path | |
|---|---|
| `NTCamera.apk` | stored with Git LFS (`git lfs pull` after cloning). Built from `app/Android.bp` (symlinked APK) so it is dexpreopted like stock. See `patches/NTCamera.md` for its bytecode changes. |
| `libofflineproc_jni` | NTCamera's JNI for `media.offline` |
| `offlineproc/` | `libofflineproc_shim`: `IOfflineProcService`/`IOfflineProcClient` (AIDL reconstructed from Nothing's `libcamera_client`, same transaction codes and vtables) plus `OfflineParameters` and `OfflineProcClient` with Nothing's object layout. `ntcam_offlineproc`: lazy `media.offline` service. |
| `libntcam_client` | system_ext client library `libofflineproc_jni` links against |
| `app/libarcsoft_dehaze.so` | compatible engine retained from the previous APK and bundled by the Asteroids genrule |
| `shims/libntcam_session_shim` | prebuilt, see below |
| `vendor.noth.hardware.camera-service` | Nothing's algorithm HAL (`INtCamService`), run in `hal_camera_default` (QTI camera provider domain) |
| `sepolicy/` | Mirrors the stock policy for the above, plus the `platform_app`/`platform_app_36` client rules |

### Why `media.offline` exists

The JNI polls `getService("media.offline")` in an endless 500 ms loop until the
service appears. Nothing OS publishes it from cameraserver and backs it with
`/vendor/lib64/libofflinepostprocclient.so`, which Phone (3a) firmware does not
ship, so stock answers `initOffline()` with `-EINVAL` and NTCamera processes in
the camera HAL. `ntcam_offlineproc` answers the same way, and starts only while
the camera holds it.

## Updating

```sh
./extract-files.py <path to Nothing OS dump>   # regenerates makefiles too
```

Use a dump of the matching release, with `system`, `system_ext` and `vendor`.
The APK, JNI and QNN stub come from that stock dump. The stock
`system/lib64/libcamera_client.so` is copied to
`system_ext/lib64/libntcam_client.so` with its SONAME fixed; JNI's dependency
is renamed to match. The algorithm-service V1 manifest is copied from stock's
`vendor.noth.hardware.camera-service-v1.xml` to the existing module path.

Extraction applies [NTCamera-C5.0.patch](patches/NTCamera-C5.0.patch).
The APK entry records both its stock SHA1
(`8ca1c7afb3154d57f0d879520e69f4091ac9a441`) and fixed SHA1
(`5d3a69b33738e9aab66f8c5bb42e3dfec8952723`), so a stale patched APK is not
mistaken for the current input. Refresh both hashes and review the patch when
changing releases. [NTCamera.md](patches/NTCamera.md) also describes the separate
Asteroids profile fixup performed by `app/patch_ntcamera.py`. That fixup also
bundles the previous APK's dehaze engine: the new stock APK omits it even though
the dehaze wrapper changes only its build ID. Its packaged `libmpbase.so`
dependency is byte-identical to the previous APK. The engine is hash-checked
before insertion so this update preserves the existing enhancement path.

The new client library requires `libcameracompatbilityinfo` and
`lib-camera-compatibility-info-api` from Android 17. Keep the device provider's
existing postproc interface relink and session shim: updating only the APK or
replacing the shim with a sibling-device binary does not establish compatibility.

Before accepting another drop, compare native dependencies, framework lookups,
feature selection, permissions and VINTF declarations. Static extraction and
bytecode checks cannot establish working capture. On a built device with
SELinux enforcing, verify cold start, every lens, portrait, HDR/night, video,
saved output and capture while pausing/reopening the app.

## Device-tree side (not in this repo)

Add these to the device's `extract-files.py` so they survive re-extraction:

```python
lib_fixups = {
    ...
    ('libntcam_session_shim',): lib_fixup_remove,  # module lives here, keep the device buildable without it
}

blob_fixups = {
    # Nothing extended IPostProcSession with release() under the same package
    # version, so the QTI interface library breaks the in-HAL post-processing
    # path (camerapostprocservice) for every capture. Ship Nothing's under its
    # own name and relink its users to it.
    'vendor/lib64/vendor.qti.hardware.camera.postproc@1.0-nothing.so': blob_fixup()
        .fix_soname(),
    (
        'vendor/lib64/libntofflinepostproc.so',
        'vendor/lib64/vendor.qti.hardware.camera.postproc@1.0-service-impl.so',
    ): blob_fixup()
        .replace_needed('vendor.qti.hardware.camera.postproc@1.0.so', 'vendor.qti.hardware.camera.postproc@1.0-nothing.so'),
    # Load libntcam_session_shim first: it wraps hw_get_module() and tags
    # sessions from com.nothing.camera with package_name/activity_name so
    # CamX selects the Nothing pipeline.
    'vendor/bin/hw/vendor.qti.camera.provider-service_64': blob_fixup()
        .add_needed('libntcam_session_shim.so'),
    # Portrait: cbz x23 at 0xc7d8 retargeted to 0xc6ac so the node falls back
    # to the /data/vendor/camera calibration files.
    'vendor/lib64/camera/node/com.nothing.node.bokehhdr.so': blob_fixup()
        .binary_regex_replace(b'\xb7\x83\x5d\xf8\x77\xf1\xff\xb4', b'\xb7\x83\x5d\xf8\xb7\xf6\xff\xb4'),
}
```

and in `proprietary-files.txt`:

```
vendor/bin/hw/vendor.qti.camera.provider-service_64;DISABLE_CHECKELF
vendor/lib64/libntofflinepostproc.so
vendor/lib64/vendor.qti.hardware.camera.postproc@1.0-service-impl.so
vendor/lib64/vendor.qti.hardware.camera.postproc@1.0.so:vendor/lib64/vendor.qti.hardware.camera.postproc@1.0-nothing.so
```

`DISABLE_CHECKELF` is needed because the provider's new `DT_NEEDED` lives in
this repo, outside the device's soong namespace.

## Credits

- Omkar Chandorkar - repository layout, extract-utils
  camera module and the libcamera_client shim approach, from
  [ThankYouMario/proprietary_vendor_nothing_camera@b61fb25c76](https://github.com/ThankYouMario/proprietary_vendor_nothing_camera/commit/b61fb25c762a8101420f243772b089e1b6d6c0aa)
- Aniket - working Nothing Camera bring-up on
  asteroids used as a cross-reference for the post-processing interface
  relink and provider integration:
  [819622a22f](https://github.com/crdroid-asteroids/device_nothing_asteroids/commit/819622a22f79933503b60b2fb365e4b9e0173ce4),
  [1922fc8530](https://github.com/crdroid-asteroids/device_nothing_asteroids/commit/1922fc85301d5b6820aeb2a60c4ab22dc59a2e0b)
- Fuzail Mansuri - original NT-cam port and the NTCamera bytecode
  patches,
  [9982113fcf](https://github.com/fuzailmansuri/NT-cam/commit/9982113fcf4e60ba6d4c7c76e73f1f28ce8b5ac6)
- Stock Nothing OS firmware (permissions, SELinux policy, binaries used for
  reverse engineering) from
  [leddaz-dump-stash/nothing_asteroids_dump@6c10386180](https://github.com/leddaz-dump-stash/nothing_asteroids_dump/tree/6c10386180c83031c983f569c3c956ebfe8a9c27)
- Current C5.0 camera drop from
  [spike0en/nothing_archive: Asteroids_C5.0-261106-1007](https://github.com/spike0en/nothing_archive/releases/tag/Asteroids_C5.0-261106-1007).
  The extracted system, system_ext, vendor and odm images matched the release's
  published SHA256 checksums.
