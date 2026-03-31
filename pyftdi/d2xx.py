# pylint: disable-msg=too-many-lines
#
# Copyright (C) 2022 Marius Greuel
#
# SPDX-License-Identifier: BSD-3-Clause

"""libusb emulation backend for FTDI D2XX driver."""

import errno
import logging
import sys
from ctypes import (
    cdll,
    windll,
    CFUNCTYPE,
    POINTER,
    c_ubyte,
    c_ushort,
    c_uint,
    c_ulong,
    c_void_p,
    c_char_p,
    byref,
    cast,
    create_string_buffer,
)
import usb.backend
import usb.core
import usb.util
from pyftdi.ftdi import Ftdi

# pylint: disable-msg=missing-function-docstring
# pylint: disable-msg=invalid-name
# pylint: disable-msg=global-statement
# pylint: disable-msg=too-few-public-methods
# pylint: disable-msg=too-many-arguments
# pylint: disable-msg=too-many-instance-attributes

__author__ = "Marius Greuel"

__all__ = ["get_backend"]

_logger = logging.getLogger("pyftdi.d2xx")

_lib = None

CreateEventW = None
WaitForSingleObject = None
FT_GetLibraryVersion = None
FT_GetDriverVersion = None
FT_CreateDeviceInfoList = None
FT_GetDeviceInfoDetail = None
FT_OpenEx = None
FT_Close = None
FT_ResetDevice = None
FT_ResetPort = None
FT_CyclePort = None
FT_SetDtr = None
FT_ClrDtr = None
FT_SetRts = None
FT_ClrRts = None
FT_Purge = None
FT_SetFlowControl = None
FT_SetBaudRate = None
FT_SetDataCharacteristics = None
FT_SetBreakOn = None
FT_SetBreakOff = None
FT_GetModemStatus = None
FT_SetChars = None
FT_SetLatencyTimer = None
FT_GetLatencyTimer = None
FT_SetBitMode = None
FT_GetBitMode = None
FT_SetTimeouts = None
FT_SetUSBParameters = None
FT_SetEventNotification = None
FT_GetStatus = None
FT_GetQueueStatus = None
FT_Read = None
FT_Write = None
FT_ReadEE = None
FT_WriteEE = None
FT_EraseEE = None

UCHAR = c_ubyte
USHORT = c_ushort
ULONG = c_ulong
WORD = c_ushort
DWORD = c_uint
FT_STATUS = c_ulong
FT_HANDLE = c_void_p

_IN = 1
_OUT = 2

FT_OK = 0
FT_INVALID_HANDLE = 1
FT_DEVICE_NOT_FOUND = 2
FT_DEVICE_NOT_OPENED = 3
FT_IO_ERROR = 4
FT_INSUFFICIENT_RESOURCES = 5
FT_INVALID_PARAMETER = 6
FT_INVALID_BAUD_RATE = 7
FT_DEVICE_NOT_OPENED_FOR_ERASE = 8
FT_DEVICE_NOT_OPENED_FOR_WRITE = 9
FT_FAILED_TO_WRITE_DEVICE = 10
FT_EEPROM_READ_FAILED = 11
FT_EEPROM_WRITE_FAILED = 12
FT_EEPROM_ERASE_FAILED = 13
FT_EEPROM_NOT_PRESENT = 14
FT_EEPROM_NOT_PROGRAMMED = 15
FT_INVALID_ARGS = 16
FT_NOT_SUPPORTED = 17
FT_OTHER_ERROR = 18
FT_DEVICE_LIST_NOT_READY = 19

FT_DEVICE_BM = 0
FT_DEVICE_AM = 1
FT_DEVICE_100AX = 2
FT_DEVICE_UNKNOWN = 3
FT_DEVICE_2232C = 4
FT_DEVICE_232R = 5
FT_DEVICE_2232H = 6
FT_DEVICE_4232H = 7
FT_DEVICE_232H = 8
FT_DEVICE_X_SERIES = 9
FT_DEVICE_4222H_0 = 10
FT_DEVICE_4222H_1_2 = 11
FT_DEVICE_4222H_3 = 12
FT_DEVICE_4222_PROG = 13
FT_DEVICE_900 = 14
FT_DEVICE_930 = 15
FT_DEVICE_UMFTPD3A = 16
FT_DEVICE_2233HP = 17
FT_DEVICE_4233HP = 18
FT_DEVICE_2232HP = 19
FT_DEVICE_4232HP = 20
FT_DEVICE_233HP = 21
FT_DEVICE_232HP = 22
FT_DEVICE_2232HA = 23
FT_DEVICE_4232HA = 24
FT_DEVICE_232RN = 25

FT_FLAGS_OPENED = 1

FT_OPEN_BY_SERIAL_NUMBER = 1

FT_EVENT_RXCHAR = 1

FT_PURGE_RX = 1
FT_PURGE_TX = 2

FTDI_FRAC_DIV = (0, 4, 2, 1, 3, 5, 6, 7)

ERRORS = {
    FT_OK: "OK",
    FT_INVALID_HANDLE: "Invalid_handle",
    FT_DEVICE_NOT_FOUND: "Device not found",
    FT_DEVICE_NOT_OPENED: "Device not opened",
    FT_IO_ERROR: "I/O error",
    FT_INSUFFICIENT_RESOURCES: "Insufficient resources",
    FT_INVALID_PARAMETER: "Invalid parameter",
    FT_INVALID_BAUD_RATE: "Invalid baud rate",
    FT_DEVICE_NOT_OPENED_FOR_ERASE: "Device not opened for erase",
    FT_DEVICE_NOT_OPENED_FOR_WRITE: "Device not opened for write",
    FT_FAILED_TO_WRITE_DEVICE: "Failed to write device",
    FT_EEPROM_READ_FAILED: "EEPROM read failed",
    FT_EEPROM_WRITE_FAILED: "EEPROM write failed",
    FT_EEPROM_ERASE_FAILED: "EEPROM erase failed",
    FT_EEPROM_NOT_PRESENT: "EEPROM not present",
    FT_EEPROM_NOT_PROGRAMMED: "EEPROM not programmed",
    FT_INVALID_ARGS: "Unvalid arguments",
    FT_NOT_SUPPORTED: "Not supported",
    FT_OTHER_ERROR: "Other error",
    FT_DEVICE_LIST_NOT_READY: "Device list not ready",
}

USB_DESC_STRING_LANGUAGEIDS = 0
USB_DESC_STRING_MANUFACTURER = 1
USB_DESC_STRING_PRODUCT = 2
USB_DESC_STRING_SERIALNUMBER = 3

USB_REQUEST_GET_DESCRIPTOR = 0x06

USB_ERROR_INVALID_PARAM = -2
USB_ERROR_NO_DEVICE = -4
USB_ERROR_NOT_SUPPORTED = -12

_usb_errno = {
    USB_ERROR_INVALID_PARAM: errno.__dict__.get("EINVAL", None),
    USB_ERROR_NO_DEVICE: errno.__dict__.get("ENODEV", None),
    USB_ERROR_NOT_SUPPORTED: errno.__dict__.get("ENOSYS", None),
}


def _ft_function(name, *args):
    def errcheck(result, _, args):
        if result != FT_OK:
            _logger.error("%s%s=%s", name, args, result)
            raise RuntimeError(
                f"FTDI API call '{name}' failed: " + ERRORS.get(result, result)
            )

        _logger.debug("%s%s=%s", name, args, result)
        return args

    argtypes = (arg[1] for arg in args)
    paramflags = tuple((arg[0], arg[2]) for arg in args)
    prototype = CFUNCTYPE(FT_STATUS, *argtypes)
    function = prototype((name, _lib), paramflags)
    function.errcheck = errcheck
    return function


def _load_library(_):
    try:
        if sys.platform.startswith("win"):
            path = "ftd2xx.dll"
        else:
            path = "ftd2xx.so"
        _logger.info("Loading library: %s", path)
        return cdll.LoadLibrary(path)
    except OSError as ex:
        _logger.error("Failed to load FTDI D2XX driver: %s", ex)
        raise FileNotFoundError(f"Failed to load FTDI D2XX driver: {ex}") from ex


# pylint: disable-next=too-many-statements
def _load_imports():
    global CreateEventW
    global WaitForSingleObject
    global FT_GetLibraryVersion
    global FT_GetDriverVersion
    global FT_CreateDeviceInfoList
    global FT_GetDeviceInfoDetail
    global FT_OpenEx
    global FT_Close
    global FT_ResetDevice
    global FT_ResetPort
    global FT_CyclePort
    global FT_SetDtr
    global FT_ClrDtr
    global FT_SetRts
    global FT_ClrRts
    global FT_Purge
    global FT_SetFlowControl
    global FT_SetBaudRate
    global FT_SetDataCharacteristics
    global FT_SetBreakOn
    global FT_SetBreakOff
    global FT_GetModemStatus
    global FT_SetChars
    global FT_SetLatencyTimer
    global FT_GetLatencyTimer
    global FT_SetBitMode
    global FT_GetBitMode
    global FT_SetTimeouts
    global FT_SetUSBParameters
    global FT_SetEventNotification
    global FT_GetStatus
    global FT_GetQueueStatus
    global FT_Read
    global FT_Write
    global FT_ReadEE
    global FT_WriteEE
    global FT_EraseEE

    CreateEventW = windll.kernel32.CreateEventW
    WaitForSingleObject = windll.kernel32.WaitForSingleObject

    FT_GetLibraryVersion = _ft_function(
        "FT_GetLibraryVersion", (_OUT, POINTER(DWORD), "lpdwVersion")
    )

    version = FT_GetLibraryVersion()
    _logger.info(
        "FTDI Library V%X.%X.%X",
        (version >> 16) & 0xFF,
        (version >> 8) & 0xFF,
        version & 0xFF,
    )

    FT_GetDriverVersion = _ft_function(
        "FT_GetDriverVersion",
        (_IN, FT_HANDLE, "ftHandle"),
        (_OUT, POINTER(DWORD), "lpdwVersion"),
    )
    FT_CreateDeviceInfoList = _ft_function(
        "FT_CreateDeviceInfoList", (_OUT, POINTER(DWORD), "lpdwNumDevs")
    )
    FT_GetDeviceInfoDetail = _ft_function(
        "FT_GetDeviceInfoDetail",
        (_IN, DWORD, "dwIndex"),
        (_OUT, POINTER(DWORD), "lpdwFlags"),
        (_OUT, POINTER(DWORD), "lpdwType"),
        (_OUT, POINTER(DWORD), "lpdwID"),
        (_OUT, POINTER(DWORD), "lpdwLocId"),
        (_IN, c_char_p, "lpSerialNumber"),
        (_IN, c_char_p, "lpDescription"),
        (_OUT, POINTER(FT_HANDLE), "pftHandle"),
    )
    FT_OpenEx = _ft_function(
        "FT_OpenEx",
        (_IN, c_char_p, "lpSerialNumber"),
        (_IN, DWORD, "dwFlags"),
        (_OUT, POINTER(FT_HANDLE), "pHandle"),
    )
    FT_Close = _ft_function(
        "FT_Close",
        (_IN, FT_HANDLE, "ftHandle"),
    )
    FT_ResetDevice = _ft_function(
        "FT_ResetDevice",
        (_IN, FT_HANDLE, "ftHandle"),
    )
    FT_ResetPort = _ft_function(
        "FT_ResetPort",
        (_IN, FT_HANDLE, "ftHandle"),
    )
    FT_CyclePort = _ft_function(
        "FT_CyclePort",
        (_IN, FT_HANDLE, "ftHandle"),
    )
    FT_SetDtr = _ft_function(
        "FT_SetDtr",
        (_IN, FT_HANDLE, "ftHandle"),
    )
    FT_ClrDtr = _ft_function(
        "FT_ClrDtr",
        (_IN, FT_HANDLE, "ftHandle"),
    )
    FT_SetRts = _ft_function(
        "FT_SetRts",
        (_IN, FT_HANDLE, "ftHandle"),
    )
    FT_ClrRts = _ft_function(
        "FT_ClrRts",
        (_IN, FT_HANDLE, "ftHandle"),
    )
    FT_Purge = _ft_function(
        "FT_Purge",
        (_IN, FT_HANDLE, "ftHandle"),
        (_IN, ULONG, "Mask"),
    )
    FT_SetFlowControl = _ft_function(
        "FT_SetFlowControl",
        (_IN, FT_HANDLE, "ftHandle"),
        (_IN, USHORT, "FlowControl"),
        (_IN, UCHAR, "XonChar"),
        (_IN, UCHAR, "XoffChar"),
    )
    FT_SetBaudRate = _ft_function(
        "FT_SetBaudRate",
        (_IN, FT_HANDLE, "ftHandle"),
        (_IN, ULONG, "BaudRate"),
    )
    FT_SetDataCharacteristics = _ft_function(
        "FT_SetDataCharacteristics",
        (_IN, FT_HANDLE, "ftHandle"),
        (_IN, UCHAR, "WordLength"),
        (_IN, UCHAR, "StopBits"),
        (_IN, UCHAR, "Parity"),
    )
    FT_SetBreakOn = _ft_function(
        "FT_SetBreakOn",
        (_IN, FT_HANDLE, "ftHandle"),
    )
    FT_SetBreakOff = _ft_function(
        "FT_SetBreakOff",
        (_IN, FT_HANDLE, "ftHandle"),
    )
    FT_GetModemStatus = _ft_function(
        "FT_GetModemStatus",
        (_IN, FT_HANDLE, "ftHandle"),
        (_OUT, POINTER(ULONG), "pModemStatus"),
    )
    FT_SetChars = _ft_function(
        "FT_SetChars",
        (_IN, FT_HANDLE, "ftHandle"),
        (_IN, UCHAR, "EventChar"),
        (_IN, UCHAR, "EventCharEnabled"),
        (_IN, UCHAR, "ErrorChar"),
        (_IN, UCHAR, "ErrorCharEnabled"),
    )
    FT_SetLatencyTimer = _ft_function(
        "FT_SetLatencyTimer",
        (_IN, FT_HANDLE, "ftHandle"),
        (_IN, UCHAR, "ucLatency"),
    )
    FT_GetLatencyTimer = _ft_function(
        "FT_GetLatencyTimer",
        (_IN, FT_HANDLE, "ftHandle"),
        (_OUT, POINTER(UCHAR), "pucLatency"),
    )
    FT_SetBitMode = _ft_function(
        "FT_SetBitMode",
        (_IN, FT_HANDLE, "ftHandle"),
        (_IN, UCHAR, "ucMask"),
        (_IN, UCHAR, "ucEnable"),
    )
    FT_GetBitMode = _ft_function(
        "FT_GetBitMode",
        (_IN, FT_HANDLE, "ftHandle"),
        (_OUT, POINTER(UCHAR), "pucMode"),
    )
    FT_SetTimeouts = _ft_function(
        "FT_SetTimeouts",
        (_IN, FT_HANDLE, "ftHandle"),
        (_IN, ULONG, "ReadTimeout"),
        (_IN, ULONG, "WriteTimeout"),
    )
    FT_SetUSBParameters = _ft_function(
        "FT_SetUSBParameters",
        (_IN, FT_HANDLE, "ftHandle"),
        (_IN, ULONG, "ulInTransferSize"),
        (_IN, ULONG, "ulOutTransferSize"),
    )
    FT_SetEventNotification = _ft_function(
        "FT_SetEventNotification",
        (_IN, FT_HANDLE, "ftHandle"),
        (_IN, DWORD, "Mask"),
        (_IN, c_void_p, "Param"),
    )
    FT_GetStatus = _ft_function(
        "FT_GetStatus",
        (_IN, FT_HANDLE, "ftHandle"),
        (_OUT, POINTER(DWORD), "dwRxBytes"),
        (_OUT, POINTER(DWORD), "dwTxBytes"),
        (_OUT, POINTER(DWORD), "dwEventDWord"),
    )
    FT_GetQueueStatus = _ft_function(
        "FT_GetQueueStatus",
        (_IN, FT_HANDLE, "ftHandle"),
        (_OUT, POINTER(DWORD), "dwRxBytes"),
    )
    FT_Read = _ft_function(
        "FT_Read",
        (_IN, FT_HANDLE, "ftHandle"),
        (_IN, POINTER(c_ubyte), "lpBuffer"),
        (_IN, DWORD, "dwBytesToRead"),
        (_OUT, POINTER(DWORD), "lpdwBytesReturned"),
    )
    FT_Write = _ft_function(
        "FT_Write",
        (_IN, FT_HANDLE, "ftHandle"),
        (_IN, POINTER(c_ubyte), "lpBuffer"),
        (_IN, DWORD, "dwBytesToWrite"),
        (_OUT, POINTER(DWORD), "lpdwBytesWritten"),
    )
    FT_ReadEE = _ft_function(
        "FT_ReadEE",
        (_IN, FT_HANDLE, "ftHandle"),
        (_IN, DWORD, "dwWordOffset"),
        (_OUT, POINTER(WORD), "lpwValue"),
    )
    FT_WriteEE = _ft_function(
        "FT_WriteEE",
        (_IN, FT_HANDLE, "ftHandle"),
        (_IN, DWORD, "dwWordOffset"),
        (_IN, WORD, "wValue"),
    )
    FT_EraseEE = _ft_function(
        "FT_EraseEE",
        (_IN, FT_HANDLE, "ftHandle"),
    )


class _Handle:
    def __init__(self, dev):
        self.dev = dev
        self.handle = None
        self.rx_event = None
        self.available = False
        self.event_char = 0
        self.event_char_enabled = 0
        self.error_char = 0
        self.error_char_enabled = 0


class _Device:
    def __init__(
        self, flags, dev_type, dev_id, loc_id, ft_handle, serial_number, description
    ):
        self.flags = flags
        self.dev_type = dev_type
        self.dev_id = dev_id
        self.loc_id = loc_id
        self.ft_handle = ft_handle
        self.serial_number = serial_number
        self.description = description
        self.num_interfaces = self._get_num_interfaces(dev_type)
        self.default_interface = 0
        self.interface_handles = [_Handle(self) for _ in range(self.num_interfaces)]

    def _get_num_interfaces(self, dev_type):
        if dev_type in (
            FT_DEVICE_4232H,
            FT_DEVICE_4232HA,
            FT_DEVICE_4232HP,
            FT_DEVICE_4233HP,
        ):
            return 4

        if dev_type in (
            FT_DEVICE_2232C,
            FT_DEVICE_2232H,
            FT_DEVICE_2232HA,
            FT_DEVICE_2232HP,
            FT_DEVICE_2233HP,
        ):
            return 2

        return 1


class _DeviceDescriptor:
    def __init__(self, dev):
        self.bLength = 0x12
        self.bDescriptorType = 0x01
        self.bcdUSB = 0x200
        self.bDeviceClass = 0
        self.bDeviceSubClass = 0
        self.bDeviceProtocol = 0
        self.bMaxPacketSize0 = 0x40
        self.idVendor = (dev.dev_id >> 16) & 0xFFFF
        self.idProduct = dev.dev_id & 0xFFFF
        self.bcdDevice = self._get_bcd_device(dev.dev_type)
        self.iManufacturer = 0x01
        self.iProduct = 0x02
        self.iSerialNumber = 0x03
        self.bNumConfigurations = 0x01

        self.address = dev.loc_id & 0xF
        self.bus = (dev.loc_id >> 4) & 0xF
        self.port_number = None
        self.port_numbers = None
        self.speed = None

    # pylint: disable-next=too-many-return-statements
    def _get_bcd_device(self, dev_type):
        if dev_type == FT_DEVICE_AM:
            return 0x0200
        if dev_type == FT_DEVICE_BM:
            return 0x0400
        if dev_type == FT_DEVICE_2232C:
            return 0x0500
        if dev_type == FT_DEVICE_232R:
            return 0x0600
        if dev_type in (
            FT_DEVICE_2232H,
            FT_DEVICE_2232HA,
            FT_DEVICE_2232HP,
            FT_DEVICE_2233HP,
        ):
            return 0x0700
        if dev_type in (
            FT_DEVICE_4232H,
            FT_DEVICE_4232HA,
            FT_DEVICE_4232HP,
            FT_DEVICE_4233HP,
        ):
            return 0x0800
        if dev_type in (
            FT_DEVICE_232H,
            FT_DEVICE_232HP,
            FT_DEVICE_233HP,
            FT_DEVICE_232RN,
        ):
            return 0x0900
        if dev_type == FT_DEVICE_X_SERIES:
            return 0x1000
        return 0x0900


class _ConfigurationDescriptor:
    def __init__(self, dev):
        self.bLength = 0x09
        self.bDescriptorType = 0x02
        self.wTotalLength = 0x0020
        self.bNumInterfaces = dev.num_interfaces
        self.bConfigurationValue = 0x01
        self.iConfiguration = 0x00
        self.bmAttributes = 0xA0
        self.bMaxPower = 0x2D

        self.interface = None
        self.extra = None
        self.extralen = 0
        self.extra_descriptors = None


class _InterfaceDescriptor:
    def __init__(self, intf):
        self.bLength = 0x09
        self.bDescriptorType = 0x04
        self.bInterfaceNumber = intf
        self.bAlternateSetting = 0x00
        self.bNumEndpoints = 0x02
        self.bInterfaceClass = 0xFF
        self.bInterfaceSubClass = 0xFF
        self.bInterfaceProtocol = 0xFF
        self.iInterface = 0x02

        self.endpoint = None
        self.extra = None
        self.extralen = 0
        self.extra_descriptors = None


class _EndpointDescriptor:
    def __init__(self, bEndpointAddress):
        self.bLength = 0x07
        self.bDescriptorType = 0x05
        self.bEndpointAddress = bEndpointAddress
        self.bmAttributes = 0x02
        self.wMaxPacketSize = 0x0040
        self.bInterval = 0x00
        self.bRefresh = 0x00
        self.bSynchAddress = 0x00

        self.extra = None
        self.extralen = 0
        self.extra_descriptors = None


class _D2xxError(usb.core.USBError):
    def __init__(self, strerror, error_code=USB_ERROR_NOT_SUPPORTED):
        _logger.error(strerror)
        usb.core.USBError.__init__(
            self, strerror, error_code, _usb_errno.get(error_code, None)
        )


class _D2xx(usb.backend.IBackend):
    # pylint: disable-next=too-many-locals
    def enumerate_devices(self):
        devices = []

        num_devs = FT_CreateDeviceInfoList()
        for index in range(num_devs):
            lpSerialNumber = create_string_buffer(16)
            lpDescription = create_string_buffer(64)
            flags, dev_type, dev_id, loc_id, ft_handle = FT_GetDeviceInfoDetail(
                index, lpSerialNumber, lpDescription
            )
            serial_number = lpSerialNumber.value.decode("cp1252")
            description = lpDescription.value.decode("cp1252")
            _logger.info(
                "Found device: "
                "type='%s', ID=%04X:%04X, flags=0x%08X, serial_number='%s', description='%s'",
                self._friendly_type(dev_type),
                dev_id & 0xFFFF,
                (dev_id >> 16) & 0xFFFF,
                flags,
                serial_number,
                description,
            )

            device = _Device(
                flags, dev_type, dev_id, loc_id, ft_handle, serial_number, description
            )

            if len(device.interface_handles) > 1:
                interface = ord(device.serial_number[-1]) - ord("A")
                assert 0 <= interface < len(device.interface_handles)
                device.default_interface = interface
                device.interface_handles[interface].available = True
                device.serial_number = device.serial_number[:-1]
                device.description = device.description[:-1].rstrip()
            else:
                device.default_interface = 0
                device.interface_handles[0].available = True

            if not flags & FT_FLAGS_OPENED:
                for existing_device in devices:
                    if existing_device.serial_number == device.serial_number:
                        existing_device.interface_handles[
                            device.default_interface
                        ].available = True
                        break
                else:
                    devices.append(device)

        return devices

    def get_device_descriptor(self, dev):
        _logger.info("get_device_descriptor")
        return _DeviceDescriptor(dev)

    def get_configuration_descriptor(self, dev, config):
        _logger.info("get_configuration_descriptor: config=%s", config)

        if config >= 1:
            raise IndexError("Invalid configuration index " + str(config))

        return _ConfigurationDescriptor(dev)

    def get_interface_descriptor(self, dev, intf, alt, config):
        _logger.info(
            "get_interface_descriptor: intf=%s, alt=%s, config=%s", intf, alt, config
        )

        if config >= 1:
            raise IndexError("Invalid configuration index " + str(config))
        if intf >= dev.num_interfaces:
            raise IndexError("Invalid interface index " + str(intf))
        if alt >= 1:
            raise IndexError("Invalid alternate setting index " + str(alt))

        return _InterfaceDescriptor(intf)

    def get_endpoint_descriptor(self, dev, ep, intf, alt, config):
        _logger.info(
            "get_endpoint_descriptor: ep=%s, intf=%s, alt=%s, config=%s",
            ep,
            intf,
            alt,
            config,
        )

        if ep >= 2:
            raise IndexError("Invalid endpoint index " + str(ep))
        if config >= 1:
            raise IndexError("Invalid configuration index " + str(config))
        if intf >= dev.num_interfaces:
            raise IndexError("Invalid interface index " + str(intf))
        if alt >= 1:
            raise IndexError("Invalid alternate setting index " + str(alt))

        endpoint_address = 0x80 | intf * 2 + 1 if ep == 0 else intf * 2 + 2
        return _EndpointDescriptor(endpoint_address)

    def open_device(self, dev):
        _logger.info("open_device: serial_number=%s", dev.serial_number)

        interface_handle = self._open_device_interface(dev, dev.default_interface)
        version = FT_GetDriverVersion(interface_handle.handle)
        _logger.info(
            "FTDI Driver V%X.%X.%X",
            (version >> 16) & 0xFF,
            (version >> 8) & 0xFF,
            version & 0xFF,
        )

        interface_handle.rx_event = CreateEventW(None, 0, 0, None)
        FT_SetTimeouts(interface_handle.handle, 5000, 1000)
        FT_SetEventNotification(
            interface_handle.handle, FT_EVENT_RXCHAR, interface_handle.rx_event
        )
        return interface_handle

    def close_device(self, dev_handle):
        _logger.info("close_device")
        for interface_handle in dev_handle.dev.interface_handles:
            self._close_device_interface(interface_handle)

    def set_configuration(self, dev_handle, config_value):
        _logger.info("set_configuration: config_value=%s", config_value)
        del dev_handle

    def get_configuration(self, dev_handle):
        _logger.info("get_configuration")
        del dev_handle
        return 1

    def claim_interface(self, dev_handle, intf):
        _logger.info("claim_interface: intf=%s", intf)
        interface_handle = dev_handle.dev.interface_handles[intf]
        if interface_handle.handle is None:
            self._open_device_interface(dev_handle.dev, intf)

    def release_interface(self, dev_handle, intf):
        _logger.info("release_interface: intf=%s", intf)
        interface_handle = dev_handle.dev.interface_handles[intf]
        if not interface_handle.handle is None:
            self._close_device_interface(interface_handle)

    def bulk_write(self, dev_handle, ep, intf, data, timeout):
        _logger.info(
            "bulk_write: ep=%s, intf=%s, len=%s, timeout=%s",
            ep,
            intf,
            len(data),
            timeout,
        )
        interface_handle = dev_handle.dev.interface_handles[intf]
        c_data = (c_ubyte * len(data)).from_buffer(data)
        return FT_Write(interface_handle.handle, c_data, len(data))

    def bulk_read(self, dev_handle, ep, intf, buff, timeout):
        _logger.info(
            "bulk_read: ep=%s, intf=%s, len=%s, timeout=%s",
            ep,
            intf,
            len(buff),
            timeout,
        )
        interface_handle = dev_handle.dev.interface_handles[intf]
        if len(buff) < 2:
            return 0

        status = WaitForSingleObject(interface_handle.rx_event, 10)
        if status != 0:
            return 0

        rx_bytes = FT_GetQueueStatus(interface_handle.handle)
        if rx_bytes == 0:
            return 0

        buff[0] = 0
        buff[1] = 0

        rx_bytes = min(rx_bytes, len(buff) - 2)

        c_buff = (c_ubyte * len(buff)).from_buffer(buff)
        bytes_returned = FT_Read(
            interface_handle.handle, cast(byref(c_buff, 2), POINTER(c_ubyte)), rx_bytes
        )
        return bytes_returned + 2

    def ctrl_transfer(
        self, dev_handle, bmRequestType, bRequest, wValue, wIndex, data, timeout
    ):
        _logger.info(
            "ctrl_transfer: bmRequestType=0x%02X, bRequest=0x%02X, wValue=0x%04X, wIndex=0x%04X"
            " -> %s",
            bmRequestType,
            bRequest,
            wValue,
            wIndex,
            self._decode_request(bmRequestType, bRequest, wValue),
        )
        del timeout

        if bmRequestType & 0x60 == usb.util.CTRL_TYPE_STANDARD:
            self._ctrl_transfer_standard(
                dev_handle, bmRequestType, bRequest, wValue, data
            )
        elif bmRequestType & 0x60 == usb.util.CTRL_TYPE_VENDOR:
            interface_handle = dev_handle
            if len(dev_handle.dev.interface_handles) > 1 and bRequest < 0x80:
                interface = (wIndex & 0xFF) - 1
                interface_handle = dev_handle.dev.interface_handles[interface]
                if interface_handle.handle is None:
                    self._open_device_interface(dev_handle.dev, interface)

            self._ctrl_transfer_vendor(
                interface_handle, bmRequestType, bRequest, wValue, wIndex, data
            )
        else:
            raise _D2xxError("Not implemented.", USB_ERROR_NOT_SUPPORTED)

    def _ctrl_transfer_standard(
        self, dev_handle, bmRequestType, bRequest, wValue, data
    ):
        if (
            bmRequestType & usb.util.ENDPOINT_IN
            and bRequest == USB_REQUEST_GET_DESCRIPTOR
        ):
            desc_index = wValue & 0xFF
            desc_type = (wValue >> 8) & 0xFF
            if desc_type == usb.util.DESC_TYPE_STRING:
                if desc_index == USB_DESC_STRING_LANGUAGEIDS:
                    data[0] = 0x04
                    data[1] = 0x03
                    # 0x0409 English(US)
                    data[2] = 0x09
                    data[3] = 0x04
                    return 4

                if desc_index == USB_DESC_STRING_MANUFACTURER:
                    s = "FTDI"
                elif desc_index == USB_DESC_STRING_PRODUCT:
                    s = dev_handle.dev.description
                elif desc_index == USB_DESC_STRING_SERIALNUMBER:
                    s = dev_handle.dev.serial_number
                else:
                    s = None

                if not s is None:
                    data[0] = 2 * (len(s) + 1)
                    data[1] = 0x03
                    for i, c in enumerate(s.encode("utf-16-le")):
                        data[i + 2] = c
                    return data[0]

        raise _D2xxError("Not implemented.", USB_ERROR_NOT_SUPPORTED)

    # pylint: disable-next=too-many-locals,too-many-branches,too-many-statements,too-many-return-statements
    def _ctrl_transfer_vendor(
        self, dev_handle, bmRequestType, bRequest, wValue, wIndex, data
    ):
        if bmRequestType & 0x80 == 0 and bRequest == Ftdi.SIO_REQ_RESET:
            if wValue == Ftdi.SIO_RESET_SIO:
                FT_ResetDevice(dev_handle.handle)
                return 0
            if wValue == Ftdi.SIO_RESET_PURGE_RX:
                FT_Purge(dev_handle.handle, FT_PURGE_RX)
                return 0
            if wValue == Ftdi.SIO_RESET_PURGE_TX:
                FT_Purge(dev_handle.handle, FT_PURGE_TX)
                return 0
        elif bmRequestType & 0x80 == 0 and bRequest == Ftdi.SIO_REQ_SET_MODEM_CTRL:
            if wValue & 0x0100:
                if wValue & 0x01:
                    FT_SetDtr(dev_handle.handle)
                else:
                    FT_ClrDtr(dev_handle.handle)
            if wValue & 0x0200:
                if wValue & 0x02:
                    FT_SetRts(dev_handle.handle)
                else:
                    FT_ClrRts(dev_handle.handle)
            return 0
        elif bmRequestType & 0x80 == 0 and bRequest == Ftdi.SIO_REQ_SET_FLOW_CTRL:
            FT_SetFlowControl(dev_handle.handle, wIndex & 0xFF00, 0x11, 0x13)
            return 0
        elif bmRequestType & 0x80 == 0 and bRequest == Ftdi.SIO_REQ_SET_BAUDRATE:
            value = wValue
            if self._is_legacy_device_type(dev_handle.dev.dev_type):
                value |= (wIndex & 0xFF) << 16
            else:
                value |= ((wIndex >> 8) & 0xFF) << 16

            divisor = value & 0x3FFF
            frac_div = FTDI_FRAC_DIV[(value >> 14) & 7]
            hispeed = (value >> 17) & 1
            clock = 12_000_000 if hispeed else 3_000_000
            baudrate = (clock * 8) / ((divisor * 8) + frac_div)
            FT_SetBaudRate(dev_handle.handle, round(baudrate))
            return 0
        elif bmRequestType & 0x80 == 0 and bRequest == Ftdi.SIO_REQ_SET_DATA:
            word_length = wValue & 0xF
            parity = (wValue >> 8) & 0x7
            stop_bits = (wValue >> 11) & 0x3
            line_break = (wValue >> 14) & 0x1
            FT_SetDataCharacteristics(dev_handle.handle, word_length, stop_bits, parity)
            if line_break:
                FT_SetBreakOn(dev_handle.handle)
            else:
                FT_SetBreakOff(dev_handle.handle)
            return 0
        elif (
            bmRequestType & 0x80 == 0x80 and bRequest == Ftdi.SIO_REQ_POLL_MODEM_STATUS
        ):
            status = FT_GetModemStatus(dev_handle.handle)
            data[0] = status & 0xFF
            data[1] = (status >> 8) & 0xFF
            return 0
        elif bmRequestType & 0x80 == 0 and bRequest == Ftdi.SIO_REQ_SET_EVENT_CHAR:
            dev_handle.event_char = wValue & 0xFF
            dev_handle.event_char_enabled = (wValue >> 8) & 0xFF
            FT_SetChars(
                dev_handle.handle,
                dev_handle.event_char,
                dev_handle.event_char_enabled,
                dev_handle.error_char,
                dev_handle.error_char_enabled,
            )
            return 0
        elif bmRequestType & 0x80 == 0 and bRequest == Ftdi.SIO_REQ_SET_ERROR_CHAR:
            dev_handle.error_char = wValue & 0xFF
            dev_handle.error_char_enabled = (wValue >> 8) & 0xFF
            FT_SetChars(
                dev_handle.handle,
                dev_handle.event_char,
                dev_handle.event_char_enabled,
                dev_handle.error_char,
                dev_handle.error_char_enabled,
            )
            return 0
        elif bmRequestType & 0x80 == 0 and bRequest == Ftdi.SIO_REQ_SET_LATENCY_TIMER:
            FT_SetLatencyTimer(dev_handle.handle, wValue)
            return 0
        elif (
            bmRequestType & 0x80 == 0x80 and bRequest == Ftdi.SIO_REQ_GET_LATENCY_TIMER
        ):
            data[0] = FT_GetLatencyTimer(dev_handle.handle)
            return 0
        elif bRequest == Ftdi.SIO_REQ_SET_BITMODE:
            mode = (wValue >> 8) & 0xFF
            mask = wValue & 0xFF
            FT_SetBitMode(dev_handle.handle, mask, mode)
            return 0
        elif bmRequestType & 0x80 == 0x80 and bRequest == Ftdi.SIO_REQ_READ_PINS:
            data[0] = FT_GetBitMode(dev_handle.handle)
            return 0
        elif bmRequestType & 0x80 == 0x80 and bRequest == Ftdi.SIO_REQ_READ_EEPROM:
            if len(data) < 2:
                raise _D2xxError("Invalid buffer size.", USB_ERROR_INVALID_PARAM)

            value = FT_ReadEE(dev_handle.handle, wIndex)
            data[0] = value & 0xFF
            data[1] = (value >> 8) & 0xFF
            return 0
        elif bmRequestType & 0x80 == 0 and bRequest == Ftdi.SIO_REQ_WRITE_EEPROM:
            FT_WriteEE(dev_handle.handle, wIndex)
            return 0
        elif bmRequestType & 0x80 == 0 and bRequest == Ftdi.SIO_REQ_ERASE_EEPROM:
            FT_EraseEE(dev_handle.handle)
            return 0

        raise _D2xxError("Not implemented.", USB_ERROR_NOT_SUPPORTED)

    # pylint: disable-next=too-many-branches,too-many-return-statements
    def _decode_request(self, bmRequestType, bRequest, wValue):
        if bmRequestType & 0x60 == 0:
            if bRequest == USB_REQUEST_GET_DESCRIPTOR:
                return "GET_DESCRIPTOR"
        elif bmRequestType & 0x60 == 0x40:
            if bRequest == Ftdi.SIO_REQ_RESET:
                if wValue == Ftdi.SIO_RESET_SIO:
                    return "SIO_REQ_RESET(SIO_RESET_SIO)"
                if wValue == Ftdi.SIO_RESET_PURGE_RX:
                    return "SIO_REQ_RESET(SIO_RESET_PURGE_RX)"
                if wValue == Ftdi.SIO_RESET_PURGE_TX:
                    return "SIO_REQ_RESET(SIO_RESET_PURGE_TX)"
                return "SIO_REQ_RESET"
            if bRequest == Ftdi.SIO_REQ_SET_MODEM_CTRL:
                return "SIO_REQ_SET_MODEM_CTRL"
            if bRequest == Ftdi.SIO_REQ_SET_FLOW_CTRL:
                return "SIO_REQ_SET_FLOW_CTRL"
            if bRequest == Ftdi.SIO_REQ_SET_BAUDRATE:
                return "SIO_REQ_SET_BAUDRATE"
            if bRequest == Ftdi.SIO_REQ_SET_DATA:
                return "SIO_REQ_SET_DATA"
            if bRequest == Ftdi.SIO_REQ_POLL_MODEM_STATUS:
                return "SIO_REQ_POLL_MODEM_STATUS"
            if bRequest == Ftdi.SIO_REQ_SET_EVENT_CHAR:
                return "SIO_REQ_SET_EVENT_CHAR"
            if bRequest == Ftdi.SIO_REQ_SET_ERROR_CHAR:
                return "SIO_REQ_SET_ERROR_CHAR"
            if bRequest == Ftdi.SIO_REQ_SET_LATENCY_TIMER:
                return "SIO_REQ_SET_LATENCY_TIMER"
            if bRequest == Ftdi.SIO_REQ_GET_LATENCY_TIMER:
                return "SIO_REQ_GET_LATENCY_TIMER"
            if bRequest == Ftdi.SIO_REQ_SET_BITMODE:
                mode = (wValue >> 8) & 0xFF
                if mode == Ftdi.BitMode.RESET:
                    return "SIO_REQ_SET_BITMODE(UART)"
                if mode == Ftdi.BitMode.BITBANG:
                    return "SIO_REQ_SET_BITMODE(BITBANG)"
                if mode == Ftdi.BitMode.MPSSE:
                    return "SIO_REQ_SET_BITMODE(MPSSE)"
                if mode == Ftdi.BitMode.SYNCBB:
                    return "SIO_REQ_SET_BITMODE(SYNCBB)"
                if mode == Ftdi.BitMode.MCU:
                    return "SIO_REQ_SET_BITMODE(MCU)"
                if mode == Ftdi.BitMode.OPTO:
                    return "SIO_REQ_SET_BITMODE(OPTO)"
                if mode == Ftdi.BitMode.CBUS:
                    return "SIO_REQ_SET_BITMODE(CBUS)"
                if mode == Ftdi.BitMode.SYNCFF:
                    return "SIO_REQ_SET_BITMODE(SYNCFF)"
                return "SIO_REQ_SET_BITMODE"
            if bRequest == Ftdi.SIO_REQ_READ_PINS:
                return "SIO_REQ_READ_PINS"
            if bRequest == Ftdi.SIO_REQ_READ_EEPROM:
                return "SIO_REQ_READ_EEPROM"
            if bRequest == Ftdi.SIO_REQ_WRITE_EEPROM:
                return "SIO_REQ_WRITE_EEPROM"
            if bRequest == Ftdi.SIO_REQ_ERASE_EEPROM:
                return "SIO_REQ_ERASE_EEPROM"

        return "unknown"

    def _open_device_interface(self, dev, interface):
        serial_number = dev.serial_number
        if len(dev.interface_handles) > 1:
            serial_number += chr(ord("A") + interface)

        interface_handle = dev.interface_handles[interface]
        if not interface_handle.available:
            raise _D2xxError(
                "The specified port is already in use.", USB_ERROR_NO_DEVICE
            )

        interface_handle.handle = FT_OpenEx(
            serial_number.encode("cp1252"), FT_OPEN_BY_SERIAL_NUMBER
        )
        return interface_handle

    def _close_device_interface(self, interface_handle):
        if not interface_handle.handle is None:
            FT_Close(interface_handle.handle)
            interface_handle.handle = None

    def _is_legacy_device_type(self, dev_type):
        return dev_type in (FT_DEVICE_BM, FT_DEVICE_AM, FT_DEVICE_100AX, FT_DEVICE_232R)

    # pylint: disable-next=too-many-branches,too-many-return-statements
    def _friendly_type(self, dev_type):
        if dev_type == FT_DEVICE_BM:
            return "FT232BM"
        if dev_type == FT_DEVICE_AM:
            return "FT232AM"
        if dev_type == FT_DEVICE_100AX:
            return "FT100AX"
        if dev_type == FT_DEVICE_2232C:
            return "FT2232C"
        if dev_type == FT_DEVICE_232R:
            return "FT232R"
        if dev_type == FT_DEVICE_2232H:
            return "FT2232H"
        if dev_type == FT_DEVICE_4232H:
            return "FT4232H"
        if dev_type == FT_DEVICE_232H:
            return "FT232H"
        if dev_type == FT_DEVICE_X_SERIES:
            return "FTX"
        if dev_type == FT_DEVICE_4222H_0:
            return "FT4222H"
        if dev_type == FT_DEVICE_4222H_1_2:
            return "FT4222H"
        if dev_type == FT_DEVICE_4222H_3:
            return "FT4222H"
        if dev_type == FT_DEVICE_4222_PROG:
            return "FT4222"
        if dev_type == FT_DEVICE_900:
            return "FT900"
        if dev_type == FT_DEVICE_930:
            return "FT930"
        if dev_type == FT_DEVICE_UMFTPD3A:
            return "UMFTPD3A"
        if dev_type == FT_DEVICE_2233HP:
            return "FT2233HP"
        if dev_type == FT_DEVICE_4233HP:
            return "FT4233HP"
        if dev_type == FT_DEVICE_2232HP:
            return "FT2232HP"
        if dev_type == FT_DEVICE_4232HP:
            return "FT4232HP"
        if dev_type == FT_DEVICE_233HP:
            return "FT233HP"
        if dev_type == FT_DEVICE_232HP:
            return "FT232HP"
        if dev_type == FT_DEVICE_2232HA:
            return "FT2232HA"
        if dev_type == FT_DEVICE_4232HA:
            return "FT4232HA"
        if dev_type == FT_DEVICE_232RN:
            return "FT232RN"
        return "UNKNOWN"


def get_backend(find_library=None):
    """Get the libusb emulation backend for the FTDI D2XX driver."""
    global _lib
    try:
        if _lib is None:
            _lib = _load_library(find_library)
            _load_imports()

        num_devs = FT_CreateDeviceInfoList()
        if num_devs == 0:
            return None

        return _D2xx()
    # pylint: disable-next=broad-except
    except Exception:
        _logger.error("Error loading pyftdi.d2xx backend", exc_info=True)
        return None
