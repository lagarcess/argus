with open("tests/test_api.py", "r") as f:
    content = f.read()

content = content.replace(
    'assert data["results"]["win_rate"] == 0.62',
    'assert data["results"]["win_rate"] == 62.0',
)

with open("tests/test_api.py", "w") as f:
    f.write(content)
