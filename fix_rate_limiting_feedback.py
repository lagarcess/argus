with open("tests/test_rate_limiting.py", "r") as f:
    content = f.read()

content = content.replace("mock_user_free.remaining_quota = 0\n\n    class MockDatetime:", "class MockDatetime:")
content = content.replace("""    request = MagicMock(spec=Request)
    request.client.host = "1.2.3.4"


    # 100 requests per minute for free tier""", """    # 100 requests per minute for free tier""")

with open("tests/test_rate_limiting.py", "w") as f:
    f.write(content)
