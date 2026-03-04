import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from app.email_sync import EmailSyncService
from app.database import EmailAccount


class TestFetchDates:
    """测试 _fetch_dates 方法"""

    @pytest.fixture
    def mock_account(self):
        """创建模拟的邮箱账户"""
        account = MagicMock(spec=EmailAccount)
        account.id = 1
        account.email = "test@example.com"
        account.imap_server = "imap.test.com"
        account.imap_port = 993
        account.auth_code = "encrypted_code"
        return account

    @pytest.fixture
    def service(self, mock_account):
        """创建服务实例，跳过 __init__ 中的解密操作"""
        with patch('app.email_sync.decrypt', return_value='decrypted_code'):
            service = EmailSyncService(mock_account)
            service.imap = MagicMock()
            return service

    def test_fetch_dates_empty_list(self, service):
        """测试空邮件列表"""
        result = service._fetch_dates([])
        assert result == {}

    def test_fetch_dates_single_email(self, service):
        """测试单封邮件日期获取"""
        # 模拟 IMAP 返回
        service.imap.fetch.return_value = (
            "OK",
            [
                (b'1 (BODY[HEADER.FIELDS (DATE)] {40}', b'Date: Mon, 01 Jan 2024 12:00:00 +0800\r\n\r\n')
            ]
        )

        result = service._fetch_dates([b'1'])
        assert b'1' in result
        assert isinstance(result[b'1'], datetime)

    def test_fetch_dates_multiple_emails(self, service):
        """测试多封邮件日期获取"""
        # 模拟 IMAP 返回多封邮件
        service.imap.fetch.return_value = (
            "OK",
            [
                (b'1 (BODY[HEADER.FIELDS (DATE)] {40}', b'Date: Mon, 01 Jan 2024 12:00:00 +0800\r\n\r\n'),
                (b'2 (BODY[HEADER.FIELDS (DATE)] {40}', b'Date: Tue, 02 Jan 2024 12:00:00 +0800\r\n\r\n'),
            ]
        )

        result = service._fetch_dates([b'1', b'2'])
        assert len(result) == 2
        assert b'1' in result
        assert b'2' in result

    def test_fetch_dates_invalid_date(self, service):
        """测试无效日期格式"""
        service.imap.fetch.return_value = (
            "OK",
            [
                (b'1 (BODY[HEADER.FIELDS (DATE)] {20}', b'Date: invalid date\r\n\r\n')
            ]
        )

        result = service._fetch_dates([b'1'])
        # 无效日期应该被跳过
        assert b'1' not in result

    def test_fetch_dates_imap_error(self, service):
        """测试 IMAP 错误"""
        service.imap.fetch.return_value = ("NO", [])

        result = service._fetch_dates([b'1'])
        assert result == {}

    def test_fetch_dates_batch_processing(self, service):
        """测试批量处理（超过 500 封）"""
        # 创建 600 个邮件 ID
        email_ids = [str(i).encode() for i in range(1, 601)]

        # 模拟第一批返回
        first_batch = [
            (f'{i} (BODY[HEADER.FIELDS (DATE)] {{40}}'.encode(), b'Date: Mon, 01 Jan 2024 12:00:00 +0800\r\n\r\n')
            for i in range(1, 501)
        ]
        # 模拟第二批返回
        second_batch = [
            (f'{i} (BODY[HEADER.FIELDS (DATE)] {{40}}'.encode(), b'Date: Tue, 02 Jan 2024 12:00:00 +0800\r\n\r\n')
            for i in range(501, 601)
        ]

        service.imap.fetch.side_effect = [
            ("OK", first_batch),
            ("OK", second_batch)
        ]

        result = service._fetch_dates(email_ids)

        # 验证 fetch 被调用两次（两批）
        assert service.imap.fetch.call_count == 2
        # 验证结果数量
        assert len(result) == 600

    def test_fetch_dates_exception_handling(self, service):
        """测试 IMAP 异常处理"""
        service.imap.fetch.side_effect = Exception("Connection lost")

        result = service._fetch_dates([b'1'])
        # 异常应该被捕获，返回空字典
        assert result == {}

    def test_fetch_dates_malformed_response(self, service):
        """测试畸形响应数据"""
        # 模拟返回非 tuple 类型的数据
        service.imap.fetch.return_value = (
            "OK",
            [b'some non-tuple data']
        )

        result = service._fetch_dates([b'1'])
        # 畸形数据应该被跳过
        assert result == {}

    def test_fetch_dates_missing_date_header(self, service):
        """测试缺少 Date 头的邮件"""
        service.imap.fetch.return_value = (
            "OK",
            [
                (b'1 (BODY[HEADER.FIELDS (DATE)] {10}', b'\r\n\r\n')
            ]
        )

        result = service._fetch_dates([b'1'])
        # 没有 Date 头的邮件不应该出现在结果中
        assert b'1' not in result

    def test_fetch_dates_various_date_formats(self, service):
        """测试多种日期格式"""
        test_cases = [
            (b'1', b'Date: 01 Jan 2024 12:00:00 +0800\r\n\r\n'),
            (b'2', b'Date: Mon, 01 Jan 2024 12:00:00 GMT\r\n\r\n'),
            (b'3', b'Date: 1 Jan 2024 12:00:00 -0000\r\n\r\n'),
        ]

        service.imap.fetch.return_value = (
            "OK",
            [
                (email_id + b' (BODY[HEADER.FIELDS (DATE)] {40}', date_bytes)
                for email_id, date_bytes in test_cases
            ]
        )

        email_ids = [tc[0] for tc in test_cases]
        result = service._fetch_dates(email_ids)

        # 所有有效格式都应该被解析
        assert len(result) == 3
