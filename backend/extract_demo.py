"""
三元组提取示例
演示如何使用 DeepSeek LLM 从文本中提取知识图谱三元组
"""

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from typing import List

load_dotenv()

# 配置 LLM
llm = ChatOpenAI(
    temperature=0,
    model_name="deepseek-chat",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
)

# 定义输出结构
class Triple(BaseModel):
    subject: str = Field(description="三元组的主体（实体）")
    predicate: str = Field(description="关系/谓词")
    object: str = Field(description="三元组的客体（实体）")
    confidence: float = Field(description="置信度分数 0-1")
    span: str = Field(description="原文片段")

class TriplesOutput(BaseModel):
    triples: List[Triple] = Field(description="提取的三元组列表")

# 创建解析器
parser = JsonOutputParser(pydantic_object=TriplesOutput)

# 优化的中文提取 Prompt
prompt_template = """你是一个专业的知识图谱构建助手。请从以下文本中提取所有有意义的三元组。

要求：
1. 三元组格式：(主体, 关系, 客体)
2. 主体和客体应该是实体（人、地点、概念、事物等）
3. 关系应该是动词或描述性短语
4. 每个三元组必须是事实性的，不要推测
5. 提供置信度分数（0-1）和原文片段

示例：
文本："爱因斯坦提出了相对论，这是现代物理学的基础。"
输出：
- (爱因斯坦, 提出, 相对论) [confidence: 0.95, span: "爱因斯坦提出了相对论"]
- (相对论, 是基础, 现代物理学) [confidence: 0.90, span: "这是现代物理学的基础"]

请按照以下 JSON 格式返回：
{format_instructions}

文本：
{text}
"""

prompt = PromptTemplate(
    template=prompt_template,
    input_variables=["text"],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)

# 创建处理链
chain = prompt | llm | parser

def extract_triples(text: str) -> List[dict]:
    """
    从文本中提取三元组
    
    Args:
        text: 输入文本
        
    Returns:
        三元组列表
    """
    try:
        result = chain.invoke({"text": text})
        triples = result.get("triples", [])
        
        # 转换为字典列表
        triples_list = []
        for t in triples:
            if isinstance(t, dict):
                triples_list.append(t)
            else:
                triples_list.append(t.dict() if hasattr(t, 'dict') else t.model_dump())
        
        return triples_list
    except Exception as e:
        print(f"提取错误: {e}")
        import traceback
        traceback.print_exc()
        return []

# 示例文本
sample_texts = [
    """
    量子力学是物理学的一个基本分支，用于描述微观粒子的行为。
    薛定谔方程是量子力学的核心方程，由奥地利物理学家薛定谔在1926年提出。
    这个方程描述了量子系统的波函数如何随时间演化。
    """,
    
    """
    深度学习是机器学习的一个子领域，使用多层神经网络来学习数据的表示。
    卷积神经网络（CNN）特别适合处理图像数据，在计算机视觉任务中表现出色。
    循环神经网络（RNN）则擅长处理序列数据，如文本和时间序列。
    """,
    
    """
    北京是中国的首都，位于华北平原北部。
    故宫是北京最著名的景点之一，曾是明清两代的皇家宫殿。
    长城是中国古代的军事防御工程，东起山海关，西至嘉峪关。
    """
]

if __name__ == "__main__":
    print("=" * 60)
    print("🤖 三元组提取示例")
    print("=" * 60)
    
    for i, text in enumerate(sample_texts, 1):
        print(f"\n📄 示例 {i}:")
        print(f"文本: {text.strip()[:100]}...")
        print("\n提取的三元组:")
        
        triples = extract_triples(text)
        
        if triples:
            for j, triple in enumerate(triples, 1):
                print(f"\n  {j}. ({triple['subject']}) --[{triple['predicate']}]--> ({triple['object']})")
                print(f"     置信度: {triple['confidence']:.2f}")
                print(f"     原文: \"{triple['span']}\"")
        else:
            print("  ❌ 未提取到三元组")
        
        print("\n" + "-" * 60)
    
    print("\n✅ 提取完成！")
    print("\n💡 提示：你可以修改 sample_texts 列表来测试其他文本")
