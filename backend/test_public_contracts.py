"""官网聚合接口的数据契约测试，不依赖数据库连接。"""
import unittest

from app.api.v1.public import ContactRequest, _amount_level


class PublicContractTests(unittest.TestCase):
    def test_amount_level_contract(self):
        self.assertEqual(_amount_level(None), "未披露")
        self.assertEqual(_amount_level(50), "100万以下")
        self.assertEqual(_amount_level(1000), "500–2000万")
        self.assertEqual(_amount_level(12000), "1亿以上")

    def test_contact_payload_contract(self):
        payload = ContactRequest(name="测试用户", org="测试单位", contact="test@example.com", type="feedback", description="页面反馈")
        self.assertEqual(payload.contact, "test@example.com")
        self.assertEqual(payload.type, "feedback")

    def test_contact_payload_rejects_short_contact(self):
        with self.assertRaises(Exception):
            ContactRequest(contact="x")


if __name__ == "__main__":
    unittest.main()
