#
# SPDX-FileCopyrightText: Paranoid Android
# SPDX-License-Identifier: Apache-2.0
#

TARGET_EXCLUDE_APERTURE := true

PRODUCT_PACKAGES += \
    libntcam_session_shim \
    libofflineproc_shim

PRODUCT_COPY_FILES += \
    vendor/nothing/camera/configs/init.nothing.camera.rc:$(TARGET_COPY_OUT_SYSTEM_EXT)/etc/init/init.nothing.camera.rc

PRODUCT_SYSTEM_EXT_PROPERTIES += \
    persist.vendor.camera.privapp.list=com.nothing.camera \
    ro.com.google.lens.oem_camera_package=com.nothing.camera

$(call inherit-product, vendor/nothing/camera/camera-vendor.mk)
