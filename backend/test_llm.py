import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")
base_url = os.getenv("DEEPSEEK_BASE_URL")

print(f"API Key: {api_key[:5]}...{api_key[-5:] if api_key else 'None'}")
print(f"Base URL: {base_url}")

try:
    llm = ChatOpenAI(
        temperature=0,
        model_name="deepseek-chat",
        api_key=api_key,
        base_url=base_url
    )
    
    print("\nSending test message...")
    response = llm.invoke("Hello, are you working?")
    print(f"\nResponse: {response.content}")
    print("\n✅ LLM Connection Successful!")
    
except Exception as e:
    print(f"\n❌ LLM Connection Failed: {e}")
    import traceback
    traceback.print_exc()
