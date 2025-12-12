# 🧠 LLM + Neo4j 知识图谱项目

基于 LLM + Neo4j 的知识图谱构建与可视化系统，支持文档上传、自动三元组提取、图谱可视化和智能问答。

## ✨ 核心功能
- 📄 文档上传：支持 TXT、PDF、Markdown 等格式
- 🤖 智能提取：使用 DeepSeek LLM 自动提取三元组（主体-关系-客体）
- 📊 图谱存储：Neo4j 图数据库持久化存储
- 🎨 可视化：Cytoscape.js 交互式图谱展示
- 💬 智能问答：基于知识图谱的 GraphRAG 聊天

## 🏗️ 技术架构
```
前端 (HTML) ── Cytoscape.js 图谱可视化
      │ HTTP
Flask 后端 ── 文件上传、API 路由
LangChain ── 三元组提取 Prompt
DeepSeek LLM ── 自然语言理解
Neo4j Driver ── 图数据库操作
      │ Bolt/Neo4j Protocol
Neo4j Desktop ── 图数据库
```

## 📦 项目结构
```
llmgnn/
├── backend/
│   ├── app.py              # Flask 主应用
│   ├── requirements.txt    # Python 依赖
│   ├── .env                # 环境变量配置
│   └── templates/
│       └── index.html      # 前端页面
├── static/                 # 前端静态资源
├── README.md               # 项目文档
├── .gitignore              # 忽略文件配置
├── 数据文件.txt/.md        # 示例数据
```

## 🚀 快速开始

### 1️⃣ 启动 Neo4j Desktop
- URI: `neo4j://127.0.0.1:7687`
- 用户名: `neo4j`
- 密码: `12345678`

### 2️⃣ 安装依赖
```bash
cd backend
../venv/Scripts/activate
pip install -r requirements.txt
```

### 3️⃣ 配置环境变量
编辑 `backend/.env`：
```
NEO4J_URI=neo4j://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=12345678
DEEPSEEK_API_KEY=你的API密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

### 4️⃣ 启动服务
```bash
python app.py
```
访问：http://localhost:8000

## 📖 API 示例

- 上传文件并提取三元组
  ```bash
  POST /api/upload
  Content-Type: multipart/form-data
  file: <your_file.txt>
  ```
- 获取图谱数据
  ```bash
  GET /api/graph?seed_id=量子力学&depth=2
  ```
- 智能问答
  ```bash
  POST /api/chat
  Content-Type: application/json
  {
    "node_id": "量子力学",
    "message": "什么是薛定谔方程？"
  }
  ```

## 📚 参考资源
- [Neo4j 官方文档](https://neo4j.com/docs/)
- [LangChain 文档](https://python.langchain.com/)
- [Cytoscape.js 文档](https://js.cytoscape.org/)
- [DeepSeek API](https://platform.deepseek.com/)

## 🤝 贡献
欢迎提交 Issue 和 Pull Request！

## 📄 许可证
MIT License
