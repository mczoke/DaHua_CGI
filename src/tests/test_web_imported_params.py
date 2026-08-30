import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.device_manager import DeviceInfo
import web.app as web_app
from web.app import _build_imported_config_commands, _get_device_config_variables, _serialize_device_snapshot


def test_imported_config_variables_filter_to_cgi_parameters():
    device = DeviceInfo(
        index=0,
        ip="10.0.0.1",
        variables={
            "VideoWidget[0].CustomTitle[1].Text": "一号门",
            "OSD文字": "不会自动执行",
        },
    )

    assert _get_device_config_variables(device) == {
        "VideoWidget[0].CustomTitle[1].Text": "一号门",
    }


def test_build_imported_config_commands_deduplicates_parameters():
    devices = [
        DeviceInfo(
            index=0,
            ip="10.0.0.1",
            variables={"VideoWidget[0].CustomTitle[1].Text": "一号门"},
        ),
        DeviceInfo(
            index=1,
            ip="10.0.0.2",
            variables={"VideoWidget[0].CustomTitle[1].Text": "二号门"},
        ),
    ]

    assert _build_imported_config_commands(devices) == [
        "VideoWidget[0].CustomTitle[1].Text={VideoWidget[0].CustomTitle[1].Text}",
    ]


def test_serialize_device_snapshot_summarizes_result_without_device_cycle():
    device = DeviceInfo(index=0, ip="10.0.0.1")
    device.result = {
        "device": device,
        "ip": "10.0.0.1",
        "total_commands": 1,
        "success_commands": 1,
        "failed_commands": 0,
    }

    snapshot = _serialize_device_snapshot(device)

    assert "device" not in snapshot["result"]
    assert snapshot["result"]["total_commands"] == 1


def test_delete_devices_rejects_empty_indices_without_deleting():
    old_devices = list(web_app._device_loader.devices)
    web_app._device_loader.devices = [
        DeviceInfo(index=0, ip="10.0.0.1"),
        DeviceInfo(index=1, ip="10.0.0.2"),
    ]
    try:
        with web_app.app.test_client() as client:
            response = client.post("/api/devices/delete", json={"indices": []})

        assert response.status_code == 400
        assert len(web_app._device_loader.devices) == 2
    finally:
        web_app._device_loader.devices = old_devices
