import os
import sys
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from typing import List

load_dotenv()

# Define Pydantic models
class Triple(BaseModel):
    subject: str = Field(description="The subject of the triple")
    predicate: str = Field(description="The relationship/predicate")
    object: str = Field(description="The object of the triple")
    confidence: float = Field(description="Confidence score between 0 and 1")
    span: str = Field(description="The original text span")

class TriplesOutput(BaseModel):
    triples: List[Triple] = Field(description="List of extracted triples")

# Setup LLM
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

llm = ChatOpenAI(
    temperature=0, 
    model_name="deepseek-chat", 
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL
)

# Test text
test_text = "张三是一名软件工程师。他在北京工作。北京是中国的首都。"

print(f"Testing extraction with text: {test_text}\n")

parser = JsonOutputParser(pydantic_object=TriplesOutput)

prompt_template = """You are an assistant that extracts factual triples (subject, predicate, object) from the following text.
Return a JSON that matches this schema:
{format_instructions}

Text:
{text}
"""

prompt = PromptTemplate(
    template=prompt_template, 
    input_variables=["text"], 
    partial_variables={"format_instructions": parser.get_format_instructions()}
)

chain = prompt | llm | parser

try:
    print("Calling LLM...")
    result = chain.invoke({"text": test_text})
    print(f"\n✅ Result type: {type(result)}")
    print(f"✅ Result: {result}")
    
    triples = result.get("triples", [])
    print(f"\n✅ Number of triples: {len(triples)}")
    
    for i, t in enumerate(triples, 1):
        print(f"\nTriple {i}:")
        if isinstance(t, dict):
            print(f"  Subject: {t.get('subject')}")
            print(f"  Predicate: {t.get('predicate')}")
            print(f"  Object: {t.get('object')}")
            print(f"  Confidence: {t.get('confidence')}")
        else:
            triple_dict = t.dict() if hasattr(t, 'dict') else t.model_dump()
            print(f"  Subject: {triple_dict.get('subject')}")
            print(f"  Predicate: {triple_dict.get('predicate')}")
            print(f"  Object: {triple_dict.get('object')}")
            print(f"  Confidence: {triple_dict.get('confidence')}")
            
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
