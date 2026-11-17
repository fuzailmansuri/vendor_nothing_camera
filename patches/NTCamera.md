# NTCamera C5.0 compatibility changes

Source: [Asteroids_C5.0-261106-1007](https://github.com/spike0en/nothing_archive/releases/tag/Asteroids_C5.0-261106-1007),
NTCamera **17.0.00.78.04**, version code `170007804`, eight DEX files.

## Extraction patch

`extract-files.py` applies [NTCamera-C5.0.patch](NTCamera-C5.0.patch) to the
stock APK. Five classes contain the six changed methods:

| Class / method | Change |
| --- | --- |
| `UFSManager.saveImage(long, NtCamUfsImage, boolean)` | Cache the save handler, return `false` if it is absent, and return the actual result of `Handler.post()`. A failed enqueue must not claim the image was saved. |
| `UFSManager.updateRequestPriority(long)` | Use one handler reference for removal/scheduling and return when it is absent. |
| `NcfBokehMode.getCalibrationData()` | Skip null or empty `QC_DUAL_MODULE_INFO` before logging its length/first byte. Preserve the existing calibration-data lookup. |
| `SettingCharacteristics.init(int)` | Replace a negative initial camera ID with rear camera ID `0` before querying characteristics. |
| `SettingContext.getCameraId()` | Return `0` for a negative stored ID. |
| `AbstractBaseMode.lambda$deleteProcessPacket$1(...)` | Handle `IllegalArgumentException` in the existing pending-capture query/error regions, alongside stock's security/database handling. |

`UFSClient.saveRawImg()` propagates the save result. The inspected QCOM/common
capture callers set `isUfsSave` from it and transfer image ownership to UFS only
on success. The common and simulation callers continue into
`NcfAlgoPostTask.addImage()` on failure. Returning `false` therefore retains the
existing in-process route rather than acknowledging a dropped background save.
This is a static caller trace, not a device capture result.

The new stock APK already catches `Error` around ProxyCameraDevice construction,
analytics/Kafka setup and cache parsing. Its `AbstractModeImpl` pending cleanup
already catches `Exception`/`Error`, and `AbstractModeImpl$1` handles invalid
queries. Review the new methods when updating; do not blindly transplant every
old APK hunk or its register numbers.

The stock APK SHA1 is `8ca1c7afb3154d57f0d879520e69f4091ac9a441`; after the
extraction patch it is `5d3a69b33738e9aab66f8c5bb42e3dfec8952723`. Both appear in
`proprietary-files.txt`. The fixed hash belongs to the APK encoded by the
repository's bundled apktool; refreshing a patch/tool requires verifying and
updating the result hash too.

## Asteroids profile selection

The optional Asteroids genrule runs `app/patch_ntcamera.py` after extraction.
It changes two property-reader instructions in `classes5.dex`:

- `ProductConfig.<clinit>` uses the existing `"Asteroids"` string for device
  selection instead of the ROM's `ro.product.device` identity.
- `FeatureConfigParser.initPropertyValue` uses the same string to select the
  shipped `ConfigMapAsteroids` or `ConfigMapAsteroidsPlus` classes.

The SKU still comes from `NTF_ASTEROIDS_PLUS` and the device's feature masks.
The fixup neither replaces `ro.product.device` globally nor changes those masks.
It checks the exact input DEX hash and both original instructions, updates the
DEX checksum/signature, and rejects an unknown APK revision. Other APK members
are copied unchanged except obsolete signing metadata and the retained dehaze
engine described below; normal platform signing remains owned by
`android_app_import`.

Input `classes5.dex` SHA256:
`4f4ef741ef88751b9eadc56cffbab1b0b772d8903d9b3d87931c5e9cd6e98310`.
Profile-fixed SHA256:
`0c7429603a2f336e30e9ad766a6f9c5b8389a4913c2973772bd2395f520d131b`.
Offsets and instruction bytes live in `app/patch_ntcamera.py` and must be
relocated from the actual methods for the next APK release.

Run the host checks without starting a ROM build:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s app -p 'test_patch_ntcamera.py' -v
```

The five tests cover limited byte changes and valid DEX checksums, idempotence,
rejection of changed/truncated bytecode, preservation of the other seven DEX
files/native libraries/resources/manifest, exact dehaze-engine insertion without
duplicates, rejection of an unknown engine before writing, and refusal to
overwrite either input.
Production extraction also verified both APK hashes and assembled the changed
bytecode. These checks do not run ART verification or any camera mode.

## Native and framework compatibility

The C5.0 JNI is relinked to the renamed stock client `libntcam_client.so`.
The algorithm HAL remains `vendor.noth.hardware.camera` V1. Keep the device's
Nothing postproc interface relink, `libui_shim`, and provider session shim.
The new client uses Android 17 camera compatibility libraries; the extraction
output declares them as dependencies.

The stock APK contains JNI variants for several devices. Some Anc, document,
dual-bokeh and dehaze dependencies are absent from this Asteroids dump. The
Asteroids config selects single-bokeh version `3` and dual-bokeh version `1`;
these do not select the new Anc variants. Scene/document/dehaze loaders have
stock `UnsatisfiedLinkError` handling; dehaze returns `-1` without calling its
native method if loading failed. A handled load error still loses an enhancement.

To preserve dehaze, the Asteroids genrule bundles `app/libarcsoft_dehaze.so`
from the previous port's APK (16.0.01.27.00), SHA256
`f26695afd804a162932796b709f153e870d9e9fafc454b3f456bf960ff80e086`.
The old/new `libdehaze.so` wrappers differ in exactly 20 build-ID bytes; all
other ELF sections, including executable code and dynamic symbols, match.
Their `libmpbase.so` dependency also matches byte for byte. The new APK retains
the wrapper's JNI method signature. This supplies the existing compatible
engine without substituting an unrelated device's algorithm. Its hash and any
existing APK copy are checked before writing, and repeated fixups do not add a
duplicate ZIP member. Device processing/image quality remain unverified.

Do not fill remaining optional variant gaps with unrelated device blobs or
enable additional feature bits as a workaround.

The framework shim must also expose stock's reflected `NTF_IND = 88` and
`NTF_LINEAR_VIBRATOR = 139`. Their values were read from C5.0's
`com.nothing.NtFeatures`, inherited by `NtFeaturesUtils`. Keep the current masks:
adding a constant is not evidence that the associated Nothing OS behavior is
implemented.

Before shipping, validate the compiled policy and merged VINTF, then test camera
cold start, permissions, every lens, portrait, HDR/night, video, saved output,
and pause/reopen with capture pending on the actual device in enforcing mode.
No build or hardware result is implied by this update.
