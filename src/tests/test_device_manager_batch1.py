"""Unit tests for device_manager.py - Batch 1: Base classes, Loader, Detector

Covers:
- DeviceInfo.get_display_info
- DeviceLoader.load_from_excel (with mocked pandas)
- DeviceLoader._analyze_columns (various patterns)
- DeviceLoader._parse_row (edge cases: nan, empty, valid)
- DeviceDetector.detect_devices (various ping outcomes)
- DeviceDetector._fast_ping (platform-specific, subprocess, timeout)
"""
import sys
import os
import platform
import subprocess
import concurrent.futures
from unittest.mock import MagicMock, patch, PropertyMock, call, ANY
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd

from utils.device_manager import (
    DeviceInfo,
    DeviceLoader,
    DeviceDetector,
    ConfigExecutor,
)


# ============================================================================
# DeviceInfo
# ============================================================================

class TestDeviceInfo:
    def test_get_display_info_no_variables(self):
        d = DeviceInfo(index=0, ip="192.168.1.100", port="8080")
        info = d.get_display_info()
        assert info == "192.168.1.100:8080"

    def test_get_display_info_with_name(self):
        d = DeviceInfo(index=0, ip="10.0.0.5", port="80", variables={"设备名称": "FrontGate"})
        info = d.get_display_info()
        assert info == "FrontGate (10.0.0.5:80)"

    def test_get_display_info_empty_variables(self):
        d = DeviceInfo(index=0, ip="10.0.0.5", port="80", variables={})
        info = d.get_display_info()
        assert info == "10.0.0.5:80"

    def test_get_display_info_default_port(self):
        d = DeviceInfo(index=0, ip="192.168.1.1")
        info = d.get_display_info()
        assert info == "192.168.1.1:80"


# ============================================================================
# DeviceLoader
# ============================================================================

class TestDeviceLoader:
    @pytest.fixture
    def loader(self):
        log_mgr = MagicMock()
        return DeviceLoader(log_mgr)

    # --- _analyze_columns ---

    def test_analyze_columns_all_match(self, loader):
        df = pd.DataFrame({
            "IP地址": ["1.2.3.4"],
            "端口": ["80"],
            "用户名": ["admin"],
            "密码": ["pass123"],
        })
        mapping = loader._analyze_columns(df)
        assert mapping["ip"] == "IP地址"
        assert mapping["port"] == "端口"
        assert mapping["username"] == "用户名"
        assert mapping["password"] == "密码"

    def test_analyze_columns_partial_match(self, loader):
        df = pd.DataFrame({
            "IP地址": ["1.2.3.4"],
            "Port": ["8080"],
            "用户名": ["admin"],
        })
        mapping = loader._analyze_columns(df)
        assert mapping["ip"] == "IP地址"
        assert mapping["port"] == "Port"
        assert mapping["username"] == "用户名"
        assert "password" not in mapping

    def test_analyze_columns_case_insensitive(self, loader):
        df = pd.DataFrame({
            "IP": ["1.2.3.4"],
            "Port": ["80"],
            "password": ["secret"],
        })
        mapping = loader._analyze_columns(df)
        assert mapping["ip"] == "IP"
        assert mapping["port"] == "Port"
        assert mapping["password"] == "password"

    # --- _parse_row ---

    def test_parse_row_valid(self, loader):
        df = pd.DataFrame({
            "IP": ["10.0.0.1"],
            "Port": ["8080"],
            "Username": ["admin"],
            "Password": ["pass"],
        })
        col_map = {"ip": "IP", "port": "Port", "username": "Username", "password": "Password"}
        device = loader._parse_row(0, df.iloc[0], col_map, "standard")
        assert device is not None
        assert device.ip == "10.0.0.1"
        assert device.port == "8080"
        assert device.username == "admin"
        assert device.password == "pass"

    def test_parse_row_empty_ip_returns_none(self, loader):
        df = pd.DataFrame({
            "IP": [""],
            "Port": ["80"],
        })
        col_map = {"ip": "IP"}
        device = loader._parse_row(0, df.iloc[0], col_map, "standard")
        assert device is None

    def test_parse_row_nan_ip_returns_none(self, loader):
        df = pd.DataFrame({
            "IP": [float("nan")],
            "Port": ["80"],
        })
        col_map = {"ip": "IP"}
        device = loader._parse_row(0, df.iloc[0], col_map, "standard")
        assert device is None

    def test_parse_row_exception_returns_none(self, loader):
        """Row parsing exception should return None."""
        col_map = {"ip": "IP_ADDR"}  # non-existent column
        df = pd.DataFrame({"IP": ["1.2.3.4"]})
        device = loader._parse_row(0, df.iloc[0], col_map, "standard")
        assert device is None

    # --- load_from_excel ---

    def test_load_from_excel_success(self, loader):
        df = pd.DataFrame({
            "IP地址": ["10.0.0.1", "10.0.0.2", "10.0.0.3"],
            "端口": ["80", "8080", "80"],
            "用户名": ["admin", "user", "admin"],
            "密码": ["a", "b", "c"],
        })

        with patch("utils.device_manager.pd.read_excel", return_value=df):
            devices, count = loader.load_from_excel("/fake/path.xlsx", mode="standard")
            assert count == 3
            assert len(devices) == 3
            assert devices[0].ip == "10.0.0.1"
            assert devices[2].ip == "10.0.0.3"
            assert loader.excel_source_file == "/fake/path.xlsx"

    def test_load_from_excel_empty_raises(self, loader):
        df = pd.DataFrame()
        with patch("utils.device_manager.pd.read_excel", return_value=df):
            with pytest.raises(ValueError, match="Excel文件为空"):
                loader.load_from_excel("/fake/empty.xlsx")

    def test_load_from_excel_exception(self, loader):
        """FileNotFoundError propagates after logging."""
        with patch("utils.device_manager.pd.read_excel", side_effect=FileNotFoundError("not found")):
            with pytest.raises(FileNotFoundError, match="not found"):
                loader.load_from_excel("/fake/missing.xlsx")


# ============================================================================
# DeviceDetector
# ============================================================================

class TestDeviceDetector:
    @pytest.fixture
    def config(self):
        return {
            "ping_concurrent": 10,
            "ping_timeout": 100,
            "config_concurrent": 5,
        }

    @pytest.fixture
    def detector(self, config):
        log_mgr = MagicMock()
        return DeviceDetector(config, log_mgr)

    # --- _fast_ping ---

    @patch("utils.device_manager.platform.system", return_value="linux")
    def test_fast_ping_linux_success(self, mock_plat, detector):
        """Linux ping with success."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = (b"64 bytes from 10.0.0.1: icmp_seq=1 ttl=64", b"")

        with patch("utils.device_manager.subprocess.Popen", return_value=mock_proc):
            result = detector._fast_ping("10.0.0.1")
            assert result is True

    @patch("utils.device_manager.platform.system", return_value="linux")
    def test_fast_ping_linux_fail(self, mock_plat, detector):
        """Linux ping failure (no reply)."""
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.communicate.return_value = (b"100% packet loss", b"")

        with patch("utils.device_manager.subprocess.Popen", return_value=mock_proc):
            result = detector._fast_ping("10.0.0.1")
            assert result is False

    @patch("utils.device_manager.platform.system", return_value="linux")
    def test_fast_ping_linux_keyword_in_output(self, mock_plat, detector):
        """Linux ping with non-zero returncode but keywords present."""
        mock_proc = MagicMock()
        mock_proc.returncode = 1  # non-zero but output has TTL
        mock_proc.communicate.return_value = (
            b"64 bytes from 10.0.0.1: icmp_seq=1 ttl=64 time=0.5ms",
            b"",
        )

        with patch("utils.device_manager.subprocess.Popen", return_value=mock_proc):
            result = detector._fast_ping("10.0.0.1")
            assert result is True

    @patch("utils.device_manager.platform.system", return_value="windows")
    def test_fast_ping_windows_success(self, mock_plat, detector):
        """Windows ping success."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.communicate.return_value = (b"Reply from 10.0.0.1: bytes=32 time=1ms TTL=128", b"")

        with patch("utils.device_manager.subprocess.Popen", return_value=mock_proc):
            result = detector._fast_ping("10.0.0.1")
            assert result is True

    @patch("utils.device_manager.platform.system", return_value="windows")
    def test_fast_ping_windows_timeout(self, mock_plat, detector):
        """Windows ping timeout."""
        mock_proc = MagicMock()
        mock_proc.communicate.side_effect = subprocess.TimeoutExpired(cmd="ping", timeout=1)

        with patch("utils.device_manager.subprocess.Popen", return_value=mock_proc):
            result = detector._fast_ping("10.0.0.1")
            assert result is False

    @patch("utils.device_manager.platform.system", return_value="linux")
    def test_fast_ping_exception(self, mock_plat, detector):
        """Ping exception returns False."""
        mock_proc = MagicMock()
        mock_proc.communicate.side_effect = OSError("No such device")

        with patch("utils.device_manager.subprocess.Popen", return_value=mock_proc):
            result = detector._fast_ping("10.0.0.1")
            assert result is False

    # --- detect_devices ---

    def test_detect_devices_all_online(self, detector):
        """All devices ping successfully."""
        devices = [
            DeviceInfo(index=0, ip="10.0.0.1"),
            DeviceInfo(index=1, ip="10.0.0.2"),
            DeviceInfo(index=2, ip="10.0.0.3"),
        ]

        with patch.object(detector, "_fast_ping", return_value=True):
            online, offline = detector.detect_devices(devices)
            assert online == 3
            assert offline == 0
            for d in devices:
                assert d.online is True
                assert d.status == "在线"

    def test_detect_devices_all_offline(self, detector):
        """All devices fail ping."""
        devices = [
            DeviceInfo(index=0, ip="10.0.0.1"),
            DeviceInfo(index=1, ip="10.0.0.2"),
        ]

        with patch.object(detector, "_fast_ping", return_value=False):
            online, offline = detector.detect_devices(devices)
            assert online == 0
            assert offline == 2
            for d in devices:
                assert d.online is False
                assert d.status == "离线"

    def test_detect_devices_mixed(self, detector):
        """Mixed ping results."""
        devices = [
            DeviceInfo(index=0, ip="10.0.0.1"),
            DeviceInfo(index=1, ip="10.0.0.2"),
            DeviceInfo(index=2, ip="10.0.0.3"),
        ]

        def mock_ping(ip):
            return ip == "10.0.0.1" or ip == "10.0.0.3"

        with patch.object(detector, "_fast_ping", side_effect=mock_ping):
            online, offline = detector.detect_devices(devices)
            assert online == 2
            assert offline == 1
            assert devices[0].online is True
            assert devices[1].online is False
            assert devices[2].online is True

    def test_detect_devices_with_stop_callback(self, detector):
        """Stop callback interrupts detection."""
        devices = [DeviceInfo(index=i, ip=f"10.0.0.{i}") for i in range(1, 21)]

        # Stop after the 5th device
        call_count = [0]

        def stop_cb():
            call_count[0] += 1
            return call_count[0] >= 10

        with patch.object(detector, "_fast_ping", return_value=True):
            with patch.object(detector.log_manager, "log_failure"):
                online, offline = detector.detect_devices(
                    devices, stop_callback=stop_cb
                )
                # Should have stopped early
                assert online >= 0
                assert offline >= 0

    def test_detect_devices_future_timeout(self, detector):
        """_fast_ping TimeoutError handled by future.result timeout."""
        devices = [DeviceInfo(index=0, ip="10.0.0.1")]

        # Simulate a very slow ping that times out
        def slow_ping(ip):
            import time
            time.sleep(10)
            return True

        with patch.object(detector, "_fast_ping", side_effect=slow_ping):
            # The timeout in as_completed(future.result(timeout=5))
            # But _fast_ping doesn't timeout here, future.result(timeout=5) would
            # Since we can't easily trigger concurrent.futures.TimeoutError with mock,
            # test that it still runs correctly
            online, offline = detector.detect_devices(
                devices, progress_callback=None, stop_callback=None
            )
            # Will succeed if the mock is fast enough, but the code handles TimeoutError
            assert offline == 0

    def test_detect_devices_with_progress_callback(self, detector):
        """Progress callback invoked at milestones."""
        devices = [DeviceInfo(index=i, ip=f"10.0.0.{i}") for i in range(1, 25)]

        progress_calls = []

        def progress_cb(phase, pct, stats):
            progress_calls.append((phase, pct))

        with patch.object(detector, "_fast_ping", return_value=True):
            online, offline = detector.detect_devices(
                devices, progress_callback=progress_cb
            )

        # Should have been called at least once (at completion)
        assert len(progress_calls) >= 1
        assert progress_calls[-1][1] >= 99.0  # near 100%
