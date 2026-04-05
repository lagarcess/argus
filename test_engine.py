with open("src/argus/engine.py", "r") as f:
    content = f.read()

# We need to make sure the pandas_ta import logic is completely removed from the inner loop since it's now in IndicatorAnalyzer
search_block_pandas_ta = """
        # Import pandas_ta outside the loop to avoid severe iterative overhead
        try:
            import pandas_ta as ta  # type: ignore
            has_ta = True
        except ImportError:
            has_ta = False
            logger.warning("pandas_ta not installed. TA-dependent indicators will be skipped.")
"""

if search_block_pandas_ta.strip() in content:
    content = content.replace(search_block_pandas_ta.strip(), "")
    print("Removed pandas_ta block")
else:
    print("Could not find pandas_ta block.")

with open("src/argus/engine.py", "w") as f:
    f.write(content)
