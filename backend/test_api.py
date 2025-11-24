import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

print(f"API Key: {DEEPSEEK_API_KEY[:10]}..." if DEEPSEEK_API_KEY else "No API Key")
print(f"Base URL: {DEEPSEEK_BASE_URL}")

try:
    llm = ChatOpenAI(
        temperature=0, 
        model_name="deepseek-chat", 
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL
    )
    
    print("\nTesting API connection...")
    response = llm.invoke("Hello, please respond with 'API working'")
    print(f"✅ Success! Response: {response.content}")
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
