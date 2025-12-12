# 架构总览

本项目是一个结合 LLM 与 Neo4j 的知识图谱系统，包含后端 Flask 服务、前端可视化页面、以及图数据库的持久化层。

## 组件

- 后端：Flask 提供 API（上传、提取、图查询、聊天等）
- LLM：DeepSeek（通过 LangChain 调用），用于抽取三元组
- 图数据库：Neo4j 存储实体与关系
- 前端：Cytoscape.js 展示知识图谱，Jinja 模板渲染

## 数据模型

- 节点（Entity）：属性至少包含 `name`，唯一约束
- 关系（REL）：属性包含 `predicate`、`confidence`、`source_doc`、`span`

## 关键流程

1. 上传文件或输入 URL
2. 解析文本（支持 txt/md/pdf/docx/pptx/html）
3. 发送到 LLM 提取三元组（JSON 数组输出）
4. 写入 Neo4j（合并节点与关系）
5. 前端图谱展示与交互

## API 约定

- `/api/graph` 返回 Cytoscape 兼容的 JSON：
  ```json
  {
    "nodes": [{"data": {"id": "A", "label": "A"}}],
    "edges": [{"data": {"id": "A_rel_B", "source": "A", "target": "B", "label": "rel"}}]
  }
  ```
- `/api/upload` 接收多文件，返回提取数量
- `/api/url` 从 URL 抓取文本并提取
- `/api/chat` 使用图谱上下文回答问题

## 查询策略

- 子图查询使用可变长度关系：`r*1..depth`
- 可选按 `source_doc` 过滤，当提供种子节点时使用 `ALL(rel IN r ...)`
- 结果限制：`LIMIT 100`

## 前端交互

- 拖拽上传、全局搜索、最短路径计算
- 侧边过滤、详情面板、导出子图（JSON/CSV/GraphML）

## 开发建议

- 修改提取逻辑在 `backend/app.py` 的 `run_extraction`
- 新增解析器扩展 `backend/ingestion.py`
- Neo4j 不可用时，API 返回空结果而非报错
