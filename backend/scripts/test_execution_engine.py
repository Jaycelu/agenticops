"""
执行引擎验证脚本
测试执行引擎、执行器、确认机制和审批流程
"""
import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.execution_engine import execution_engine, ExecutorType, ExecutionResult, RetryPolicy, ExecutionStatus
from services.script_executor import script_executor
from services.api_executor import api_executor
from services.notification_executor import notification_executor
from services.confirmation_service import confirmation_service
from services.approval_service import approval_service
from services.automation_orchestrator import automation_orchestrator


class ExecutionEngineTester:
    """执行引擎测试器"""

    def __init__(self):
        """初始化测试器"""
        self.test_results = []

    def log_test(self, test_name: str, passed: bool, message: str = ""):
        """
        记录测试结果

        Args:
            test_name: 测试名称
            passed: 是否通过
            message: 消息
        """
        status = "✓ PASS" if passed else "✗ FAIL"
        self.test_results.append({
            "test_name": test_name,
            "passed": passed,
            "message": message
        })
        print(f"{status}: {test_name}")
        if message:
            print(f"  {message}")

    async def test_executor_registration(self):
        """测试执行器注册"""
        print("\n=== 测试执行器注册 ===")

        # 检查执行器是否已注册
        executors = execution_engine.list_executors()

        expected_executors = ["script", "api", "notification"]
        for executor_type in expected_executors:
            if executor_type in executors:
                self.log_test(f"执行器 {executor_type} 已注册", True)
            else:
                self.log_test(f"执行器 {executor_type} 未注册", False)

    async def test_script_executor(self):
        """测试脚本执行器"""
        print("\n=== 测试脚本执行器 ===")

        # 创建一个简单的测试脚本
        import os
        test_script_path = "/tmp/test_script.sh"
        with open(test_script_path, "w") as f:
            f.write("#!/bin/bash\necho 'Hello, World!'\n")
        os.chmod(test_script_path, 0o755)

        # 测试简单脚本执行
        action_config = {
            "script_path": test_script_path,
            "timeout": 10
        }

        context = {
            "test": True
        }

        try:
            result = await script_executor.execute(1, action_config, context)
            if result.get("status") == "success":
                self.log_test("脚本执行器 - 简单脚本执行", True, f"输出: {result.get('output')}")
            else:
                self.log_test("脚本执行器 - 简单脚本执行", False, result.get("message"))
        except Exception as e:
            self.log_test("脚本执行器 - 简单脚本执行", False, str(e))

        # 清理测试脚本
        if os.path.exists(test_script_path):
            os.remove(test_script_path)

        # 测试配置验证
        valid_config = {
            "script_path": "/tmp/test.sh"
        }

        invalid_config = {
            "script_type": "shell"
        }

        if script_executor.validate_config(valid_config):
            self.log_test("脚本执行器 - 有效配置验证", True)
        else:
            self.log_test("脚本执行器 - 有效配置验证", False)

        if not script_executor.validate_config(invalid_config):
            self.log_test("脚本执行器 - 无效配置验证", True)
        else:
            self.log_test("脚本执行器 - 无效配置验证", False)

    async def test_api_executor(self):
        """测试API执行器"""
        print("\n=== 测试API执行器 ===")

        # 测试GET请求（使用公共API）
        action_config = {
            "method": "GET",
            "url": "https://httpbin.org/get",
            "timeout": 10
        }

        context = {
            "test": "true"
        }

        try:
            result = await api_executor.execute(2, action_config, context)
            if result.get("status") == "success":
                self.log_test("API执行器 - GET请求", True)
            else:
                self.log_test("API执行器 - GET请求", False, result.get("message"))
        except Exception as e:
            self.log_test("API执行器 - GET请求", False, str(e))

        # 测试配置验证
        valid_config = {
            "method": "GET",
            "url": "https://example.com"
        }

        invalid_config = {
            "method": "GET"
        }

        if api_executor.validate_config(valid_config):
            self.log_test("API执行器 - 有效配置验证", True)
        else:
            self.log_test("API执行器 - 有效配置验证", False)

        if not api_executor.validate_config(invalid_config):
            self.log_test("API执行器 - 无效配置验证", True)
        else:
            self.log_test("API执行器 - 无效配置验证", False)

    async def test_notification_executor(self):
        """测试通知执行器"""
        print("\n=== 测试通知执行器 ===")

        # 测试配置验证（不实际发送通知）
        valid_config = {
            "notification_type": "dingtalk",
            "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=xxx",
            "message": "Test notification",
            "title": "Test"
        }

        invalid_config = {
            "notification_type": "dingtalk",
            "message": "Test"
        }

        if notification_executor.validate_config(valid_config):
            self.log_test("通知执行器 - 有效配置验证", True)
        else:
            self.log_test("通知执行器 - 有效配置验证", False)

        if not notification_executor.validate_config(invalid_config):
            self.log_test("通知执行器 - 无效配置验证", True)
        else:
            self.log_test("通知执行器 - 无效配置验证", False)

    async def test_high_risk_detection(self):
        """测试高危操作检测"""
        print("\n=== 测试高危操作检测 ===")

        # 测试重启操作
        action_config = {
            "script": "reboot",
            "script_type": "shell"
        }

        is_high_risk, operation_type, risk_level = confirmation_service.is_high_risk_operation(
            ExecutorType.SCRIPT, action_config
        )

        if is_high_risk and operation_type:
            self.log_test("高危操作检测 - 重启命令", True, f"操作类型: {operation_type}, 风险等级: {risk_level}")
        else:
            self.log_test("高危操作检测 - 重启命令", False)

        # 测试安全操作
        safe_config = {
            "script": "echo 'safe command'",
            "script_type": "shell"
        }

        is_high_risk, operation_type, risk_level = confirmation_service.is_high_risk_operation(
            ExecutorType.SCRIPT, safe_config
        )

        if not is_high_risk:
            self.log_test("高危操作检测 - 安全命令", True)
        else:
            self.log_test("高危操作检测 - 安全命令", False)

        # 测试API DELETE操作
        delete_config = {
            "method": "DELETE",
            "url": "https://example.com/api/resource/123"
        }

        is_high_risk, operation_type, risk_level = confirmation_service.is_high_risk_operation(
            ExecutorType.API, delete_config
        )

        if is_high_risk and operation_type:
            self.log_test("高危操作检测 - DELETE请求", True, f"操作类型: {operation_type}, 风险等级: {risk_level}")
        else:
            self.log_test("高危操作检测 - DELETE请求", False)

    async def test_confirmation_requirement(self):
        """测试确认需求判断"""
        print("\n=== 测试确认需求判断 ===")

        # 测试高危操作需要确认
        action_config = {
            "script": "reboot",
            "script_type": "shell"
        }

        requires_confirm, reason, confirmation_info = confirmation_service.requires_confirmation(
            1, ExecutorType.SCRIPT, action_config
        )

        if requires_confirm and reason:
            self.log_test("确认需求 - 高危操作", True, f"原因: {reason}")
        else:
            self.log_test("确认需求 - 高危操作", False)

        # 测试安全操作不需要确认
        safe_config = {
            "script": "echo 'safe'",
            "script_type": "shell"
        }

        requires_confirm, reason, confirmation_info = confirmation_service.requires_confirmation(
            2, ExecutorType.SCRIPT, safe_config
        )

        if not requires_confirm:
            self.log_test("确认需求 - 安全操作", True)
        else:
            self.log_test("确认需求 - 安全操作", False)

    async def test_approval_levels(self):
        """测试审批级别"""
        print("\n=== 测试审批级别 ===")

        # 测试各风险等级对应的审批级别
        test_cases = [
            ("low", None),
            ("medium", "level_1"),
            ("high", "level_2"),
            ("critical", "level_3")
        ]

        for risk_level, expected_level in test_cases:
            approval_level = approval_service.get_approval_level(risk_level)
            actual_level = approval_level.value if approval_level else None

            if actual_level == expected_level:
                self.log_test(f"审批级别 - {risk_level}风险", True, f"期望: {expected_level}, 实际: {actual_level}")
            else:
                self.log_test(f"审批级别 - {risk_level}风险", False, f"期望: {expected_level}, 实际: {actual_level}")

        # 测试需要的审批人数
        from services.approval_service import ApprovalLevel

        required_approvers = approval_service.get_required_approvers(ApprovalLevel.LEVEL_3)
        if required_approvers == 2:
            self.log_test("审批人数 - 三级审批", True, f"需要 {required_approvers} 人审批")
        else:
            self.log_test("审批人数 - 三级审批", False, f"期望 2 人, 实际 {required_approvers} 人")

    async def test_retry_policy(self):
        """测试重试策略"""
        print("\n=== 测试重试策略 ===")

        retry_policy = RetryPolicy(max_retries=3, retry_delay=5, backoff_factor=2.0)

        # 测试重试延迟计算
        delays = [retry_policy.get_retry_delay(i) for i in range(3)]
        expected_delays = [5, 10, 20]

        if delays == expected_delays:
            self.log_test("重试策略 - 延迟计算", True, f"延迟序列: {delays}")
        else:
            self.log_test("重试策略 - 延迟计算", False, f"期望: {expected_delays}, 实际: {delays}")

        # 测试是否应该重试
        failed_result = ExecutionResult(
            status=ExecutionStatus.FAILED,
            message="Test failure"
        )

        should_retry = retry_policy.should_retry(0, failed_result)
        if should_retry:
            self.log_test("重试策略 - 首次失败应该重试", True)
        else:
            self.log_test("重试策略 - 首次失败应该重试", False)

        should_retry = retry_policy.should_retry(3, failed_result)
        if not should_retry:
            self.log_test("重试策略 - 达到最大重试次数不应重试", True)
        else:
            self.log_test("重试策略 - 达到最大重试次数不应重试", False)

    async def test_execution_result(self):
        """测试执行结果"""
        print("\n=== 测试执行结果 ===")

        # 测试成功结果
        success_result = ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            message="Execution successful",
            details={"test": "data"}
        )

        if success_result.is_success() and not success_result.is_failure():
            self.log_test("执行结果 - 成功状态", True)
        else:
            self.log_test("执行结果 - 成功状态", False)

        # 测试失败结果
        failed_result = ExecutionResult(
            status=ExecutionStatus.FAILED,
            message="Execution failed",
            error="Test error"
        )

        if not failed_result.is_success() and failed_result.is_failure():
            self.log_test("执行结果 - 失败状态", True)
        else:
            self.log_test("执行结果 - 失败状态", False)

        # 测试结果序列化
        result_dict = success_result.to_dict()
        if result_dict.get("status") == "success":
            self.log_test("执行结果 - 序列化", True)
        else:
            self.log_test("执行结果 - 序列化", False)

    async def test_orchestrator_registration(self):
        """测试编排器注册"""
        print("\n=== 测试编排器注册 ===")

        # 检查编排器是否初始化
        if automation_orchestrator:
            self.log_test("编排器 - 初始化", True)
        else:
            self.log_test("编排器 - 初始化", False)

        # 检查执行器是否注册到执行引擎
        executors = execution_engine.list_executors()
        if len(executors) >= 3:
            self.log_test("编排器 - 执行器注册", True, f"已注册 {len(executors)} 个执行器")
        else:
            self.log_test("编排器 - 执行器注册", False, f"仅注册 {len(executors)} 个执行器")

    async def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("开始执行引擎验证测试")
        print("=" * 60)

        await self.test_executor_registration()
        await self.test_script_executor()
        await self.test_api_executor()
        await self.test_notification_executor()
        await self.test_high_risk_detection()
        await self.test_confirmation_requirement()
        await self.test_approval_levels()
        await self.test_retry_policy()
        await self.test_execution_result()
        await self.test_orchestrator_registration()

        # 打印测试总结
        print("\n" + "=" * 60)
        print("测试总结")
        print("=" * 60)

        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r["passed"])
        failed_tests = total_tests - passed_tests

        print(f"总测试数: {total_tests}")
        print(f"通过: {passed_tests}")
        print(f"失败: {failed_tests}")
        print(f"通过率: {passed_tests/total_tests*100:.1f}%")

        if failed_tests > 0:
            print("\n失败的测试:")
            for result in self.test_results:
                if not result["passed"]:
                    print(f"  - {result['test_name']}: {result['message']}")

        print("=" * 60)

        return failed_tests == 0


async def main():
    """主函数"""
    tester = ExecutionEngineTester()
    success = await tester.run_all_tests()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
