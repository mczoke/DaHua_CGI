#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聚合报表收集器 — 跨多设备并发执行完成后的结果汇总

提供三个核心数据类和一个收集器：
  - AggregateReport / DeviceResultSummary / CommandSummary
  - collect() / to_dict() / to_summary_text()
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Optional, Any


# ============================================================================
# 数据结构
# ============================================================================

@dataclass
class DeviceResultSummary:
    """单设备执行结果摘要"""
    ip: str
    port: str
    status: str = "未知"          # 在线/离线/成功/部分完成/失败
    total_commands: int = 0
    success: int = 0
    failed: int = 0
    duration: float = 0.0
    last_message: str = ""


@dataclass
class CommandSummary:
    """单命令跨设备执行结果汇总"""
    command_name: str
    total_attempts: int = 0
    success: int = 0
    failed: int = 0
    avg_duration: float = 0.0
    failure_rate: float = 0.0


@dataclass
class AggregateReport:
    """聚合报表 — 跨多设备并发执行结果"""
    total_devices: int = 0
    online_devices: int = 0
    skipped_devices: int = 0
    total_commands: int = 0
    success_count: int = 0
    failed_count: int = 0
    success_rate: float = 0.0
    total_duration: float = 0.0
    per_device: List[DeviceResultSummary] = field(default_factory=list)
    per_command: Dict[str, CommandSummary] = field(default_factory=dict)
    failure_details: List[Dict] = field(default_factory=list)


# ============================================================================
# 收集器
# ============================================================================

class AggregateResultCollector:
    """
    聚合结果收集器

    用法::

        collector = AggregateResultCollector()
        report = collector.collect(results, devices, start_time)
        # 输出文本摘要
        print(collector.to_summary_text(report))
        # 序列化
        data = collector.to_dict(report)
    """

    @staticmethod
    def collect(
        results: List[dict],
        devices: List,
        start_time: Optional[datetime] = None,
    ) -> AggregateReport:
        """
        从批量执行结果汇总为报表

        :param results:  ``execute_batch`` 返回的 result dict 列表
        :param devices:  传入 ``execute_batch`` 的设备列表（含 DeviceInfo 对象）
        :param start_time:  开始执行时间戳，用于计算总耗时
        :return:  AggregateReport
        """
        report = AggregateReport()
        report.total_devices = len(devices)

        end_time = datetime.now()
        if start_time is not None:
            report.total_duration = (end_time - start_time).total_seconds()

        # 在线 / 离线分类
        online_devices = [d for d in devices if getattr(d, "online", False)]
        skipped_devices = [d for d in devices if not getattr(d, "online", False)]
        report.online_devices = len(online_devices)
        report.skipped_devices = len(skipped_devices)

        # ---- 设备维度 ----
        seen_ips: Dict[str, DeviceResultSummary] = {}
        for res in results:
            ip = res.get("ip", "unknown")
            port = str(res.get("port", ""))
            summary = DeviceResultSummary(
                ip=ip,
                port=port,
                status="成功" if res.get("success") else "部分完成",
                total_commands=res.get("total_commands", 0),
                success=res.get("success_commands", 0),
                failed=res.get("failed_commands", 0),
                duration=float(res.get("total_time", 0)),
                last_message=str(res.get("failure_details", "") or ""),
            )
            if summary.failed > 0 and summary.success == 0:
                summary.status = "失败"
            if not res.get("success") and summary.success > 0 and summary.failed > 0:
                summary.status = "部分完成"
            if summary.success == 0 and summary.failed == 0:
                summary.status = "无结果"
            seen_ips[ip] = summary

        # 补充扫描到的在线设备但未出现在 results 中的
        for d in online_devices:
            if d.ip not in seen_ips:
                seen_ips[d.ip] = DeviceResultSummary(
                    ip=d.ip,
                    port=str(getattr(d, "port", "")),
                    status="在线" if getattr(d, "online", False) else "离线",
                    last_message=getattr(d, "last_message", ""),
                )

        report.per_device = list(seen_ips.values())

        # ---- 命令维度 ----
        # 从 result 中很难直接提取单命令耗时，这里生成 summary 结构
        # 实际准确的命令维度统计需要更细粒度的传入数据
        cmd_summaries: Dict[str, CommandSummary] = {}
        for res in results:
            details = str(res.get("failure_details", ""))
            total_cmd = res.get("total_commands", 0)
            suc = res.get("success_commands", 0)
            fail = res.get("failed_commands", 0)
            cmd_name = f"设备_{res.get('ip', 'unknown')}"
            # 按 (设备, 命令索引) 粒度暂不具足，退化为设备维度的命令概要
            # 将全部计为一条"全局"命令汇总
            key = "__all_commands__"
            if key not in cmd_summaries:
                cmd_summaries[key] = CommandSummary(command_name=key)
            cmd_summaries[key].total_attempts += total_cmd
            cmd_summaries[key].success += suc
            cmd_summaries[key].failed += fail

        for cs in cmd_summaries.values():
            cs.avg_duration = report.total_duration / max(cs.total_attempts, 1)
            cs.failure_rate = (cs.failed / max(cs.total_attempts, 1)) * 100

        report.per_command = cmd_summaries

        # ---- 全局汇总 ----
        report.total_commands = sum(
            r.get("total_commands", 0) for r in results
        )
        report.success_count = sum(
            r.get("success_commands", 0) for r in results
        )
        report.failed_count = sum(
            r.get("failed_commands", 0) for r in results
        )
        all_cmds = report.success_count + report.failed_count
        report.success_rate = (
            (report.success_count / all_cmds * 100) if all_cmds > 0 else 0.0
        )

        # ---- 失败详情 ----
        for res in results:
            details = str(res.get("failure_details", ""))
            if details:
                report.failure_details.append({
                    "ip": res.get("ip", "unknown"),
                    "port": str(res.get("port", "")),
                    "detail": details,
                })

        return report

    @staticmethod
    def to_dict(report: AggregateReport) -> dict:
        """将 AggregateReport 转换为可 JSON 序列化的字典"""
        return {
            "总览": {
                "总设备数": report.total_devices,
                "在线设备数": report.online_devices,
                "跳过设备数": report.skipped_devices,
                "总命令数": report.total_commands,
                "成功数": report.success_count,
                "失败数": report.failed_count,
                "成功率": round(report.success_rate, 2),
                "总耗时(秒)": round(report.total_duration, 2),
            },
            "设备维度": [
                {
                    "IP": d.ip,
                    "端口": d.port,
                    "状态": d.status,
                    "总命令": d.total_commands,
                    "成功": d.success,
                    "失败": d.failed,
                    "耗时(秒)": round(d.duration, 2),
                    "最后消息": d.last_message,
                }
                for d in report.per_device
            ],
            "命令维度": [
                {
                    "命令": cmd_name,
                    "总尝试": cs.total_attempts,
                    "成功": cs.success,
                    "失败": cs.failed,
                    "平均耗时(秒)": round(cs.avg_duration, 2),
                    "失败率(%)": round(cs.failure_rate, 2),
                }
                for cmd_name, cs in report.per_command.items()
            ],
            "失败详情": report.failure_details,
        }

    @staticmethod
    def to_summary_text(report: AggregateReport) -> str:
        """生成易于日志输出的摘要文本"""
        lines = []
        lines.append("=" * 56)
        lines.append("  聚合报表 - 批量执行结果摘要")
        lines.append("=" * 56)
        lines.append(
            f"  设备: {report.online_devices}在线 / {report.skipped_devices}跳过 / "
            f"{report.total_devices}总计"
        )
        lines.append(
            f"  命令: {report.total_commands}总计 / "
            f"{report.success_count}成功 / {report.failed_count}失败"
        )
        lines.append(f"  成功率: {report.success_rate:.1f}%")
        lines.append(f"  总耗时: {report.total_duration:.1f}秒")
        lines.append("-" * 56)

        if report.per_device:
            lines.append("  设备维度:")
            for d in report.per_device:
                lines.append(
                    f"    {d.ip}:{d.port}  {d.status}  "
                    f"[{d.success}/{d.failed}]  {d.duration:.1f}s"
                )

        if report.failure_details:
            lines.append("-" * 56)
            lines.append("  失败详情:")
            for fd in report.failure_details:
                lines.append(f"    {fd['ip']}:{fd['port']} -> {fd['detail']}")

        lines.append("=" * 56)
        return "\n".join(lines)
