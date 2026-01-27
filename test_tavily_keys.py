import os
from tavily import TavilyClient

keys = [
    "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",
    "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",
    "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",
    "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",
    "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"
]

print(f"Testing {len(keys)} keys...\n")

for i, key in enumerate(keys):
    print(f"--- Key #{i+1}: {key[:10]}... ---")
    try:
        client = TavilyClient(api_key=key.strip())
        # Simple search to test auth
        result = client.search("test", max_results=1)
        print("✅ SUCCESS")
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
    print("")
