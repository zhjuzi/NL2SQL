好的，这是一个非常棒的项目想法，结合了大型语言模型（LLM）、向量数据库和传统的SQL数据库，并加入了自动修复的“自愈”能力，实用性很强。

我将为您提供一份详细的项目技术方案，涵盖架构设计、模块详解、技术选型、开发路线图，并专门说明如何连接您在Docker中运行的MySQL数据库。

-----

## NL2SQL智能数据查询与分析系统 - 技术方案

### 1\. 项目概述

本项目旨在构建一个自然语言到SQL（Natural Language to SQL, NL2SQL）的智能查询系统。用户可以通过自然语言（例如：“查询A公司的B信息”）与MySQL数据库进行交互，系统将自动完成以下任务：

1.  **意图理解**：准确理解用户查询的意图。
2.  **SQL生成**：将自然语言查询转换为可执行的MySQL SQL语句。
3.  **执行与自愈**：在目标MySQL数据库上执行生成的SQL，并捕获可能出现的错误。当发生错误时，系统能够分析错误信息，并尝试修正SQL后重新执行，直至成功。
4.  **结果呈现**：将最终成功的SQL语句及其查询结果返回给用户。
5.  **多轮交互**：支持基于上下文的追问和修改，实现更自然的对话式查询。

该系统将极大降低数据查询的技术门槛，使非技术人员也能轻松地从数据库中获取所需信息。

### 2\. 项目目标

  * **高准确率**：能够准确地将大部分常见业务查询转换为正确的SQL。
  * **高可用性**：具备SQL错误自动修复能力，提升查询成功率和系统鲁棒性。
  * **用户友好**：提供简洁的交互界面，支持自然的多轮对话。
  * **高扩展性**：架构设计支持未来接入更多数据源或更换更先进的语言模型。

### 3\. 技术架构

系统采用微服务化的分层架构，主要由以下几个核心部分组成：

**流程说明:**

1.  **用户输入**: 用户通过前端界面（Web/API）输入自然语言问题。
2.  **API网关**: 接收请求，并分发给后端NL2SQL服务。
3.  **意图理解与Schema检索**:
      * 后端服务首先对用户问题进行预处理（分词、实体识别等）。
      * 然后，将用户问题的 embedding（向量）与向量数据库中预存的“Schema知识”进行相似度搜索。
      * **关键点**：向量数据库中存储的不是原始数据，而是数据库的**元信息**，如：表名、字段名、字段注释、字段类型、表之间的关联关系（外键）、甚至一些字段的枚举值和示例数据。这些信息都被转换成了文本描述并向量化。
      * 通过相似度搜索，系统能快速找到与用户问题最相关的表和字段（例如，用户提到“负责人”、“身份证号”，系统能定位到`集团信息表`和`高管信息表`）。
4.  **Text2SQL生成 (核心)**:
      * 系统构建一个精确的**提示（Prompt）**，将其发送给大型语言模型（LLM，如Gemini/GPT系列）。
      * 这个Prompt包含三部分关键信息：
          * **用户问题**: "查看客户风险模块大理矿业公司负责人身份证号"
          * **相关Schema**: 从向量数据库中检索到的最相关的表结构信息（DDL语句、注释等）。
          * **指令与约束**: 指示LLM扮演一个SQL专家，生成MySQL方言的SQL，并给出一些格式要求或性能提示。
      * LLM根据Prompt生成初步的SQL语句。
5.  **SQL执行与自愈循环**:
      * **首次执行**: SQL执行模块尝试连接MySQL数据库并执行该SQL。
      * **成功**: 如果执行成功，则进入步骤6。
      * **失败**: 如果执行失败（例如，列名不存在、表名错误、语法错误），系统会捕获MySQL返回的错误信息。
      * **分析与修复**: 系统将\*\*“原始问题 + 上次失败的SQL + 具体的错误信息”\*\*作为新的上下文，重新构建Prompt，请求LLM进行修复。例如，Prompt会变成：“你上次生成的SQL（`SELECT ...`）执行时报错了（`Unknown column 'leader_name' in 'field list'`），请根据这个错误修复SQL。相关的表结构是...”。
      * LLM根据错误信息生成一个修正后的SQL，系统再次尝试执行。这个过程会循环进行，直到成功或达到最大重试次数。
6.  **结果返回**:
      * 将最终执行成功的SQL语句和查询到的数据结果格式化后，通过API返回给前端。
7.  **多轮对话**: 系统会缓存用户的对话历史（问题、生成的SQL、返回结果），以便在用户进行追问时（例如“那他们公司的注册资本是多少？”），能够理解上下文，生成基于上一轮查询的SQL。

### 4\. 核心模块详解

#### 4.1 Schema表示与向量化

这是提升NL2SQL准确率的关键。我们需要将MySQL的结构信息转化为高质量的文本描述，然后用Embedding模型将其向量化后存入向量数据库。

  * **内容**:
      * **表信息**: `CREATE TABLE`语句，并附加上用自然语言描述的表注释（例如：`-- 这张表存储了集团客户的基本工商信息`）。
      * **字段信息**: 字段名、数据类型，最重要的是**高质量的字段注释**（例如：`responsible_person VARCHAR(255) COMMENT '公司法人或主要负责人姓名'`）。
      * **关系信息**: 明确描述外键关系（例如：`-- 高管信息表的'corp_id'字段关联到集团信息表的'id'字段`）。
      * **示例数据**: 对于一些关键字段或分类字段，可以提供一些示例值，帮助LLM理解字段内容。
  * **流程**:
    1.  编写一个脚本，定期从MySQL的`information_schema`中抽取上述元数据。
    2.  对元数据进行格式化，形成结构化的文本描述。
    3.  使用一个Embedding模型（如Google text-embedding-004）将这些文本描述转换为向量。
    4.  将文本描述和其对应的向量存入向量数据库（如ChromaDB, FAISS）。

#### 4.2 Text2SQL模型与提示工程

这是系统的大脑。推荐使用能力强大的通用大模型API（如Google Gemini API）来快速启动项目。

  * **核心是构建高质量的Prompt**。一个优秀的Prompt模板如下：

<!-- end list -->

```text
### Instructions ###
You are a MySQL expert. Your task is to generate a SQL query based on the user's question and the provided database schema.
Only use the tables and columns provided in the schema.
The user's question is in Chinese. Please generate a single, executable MySQL query. Do not add any explanations or comments in the SQL itself.

### Database Schema ###
{retrieved_schema_from_vector_db}

### User Question ###
{user_question}

### SQL Query ###
```

  * **自愈循环的Prompt模板**：

<!-- end list -->

```text
### Instructions ###
You are a MySQL expert. You previously generated a SQL query that failed to execute. Your task is to fix the query based on the error message.
Only use the tables and columns provided in the schema.
The user's question is in Chinese. Please generate a single, executable MySQL query. Do not add any explanations or comments in the SQL itself.

### Database Schema ###
{retrieved_schema_from_vector_db}

### User Question ###
{user_question}

### Previous Failed SQL ###
{failed_sql}

### MySQL Error Message ###
{error_message}

### Corrected SQL Query ###
```

#### 4.3 示例演练

以用户输入“查看客户风险模块大理矿业公司负责人身份证号”为例：

1.  **检索**: 系统将问题向量化，在向量库中匹配到`集团信息表 (group_company_info)`和`高管信息表 (executive_info)`最为相关。
2.  **构建Prompt**: 将这两张表的`CREATE TABLE`语句和相关注释放入Prompt的`{retrieved_schema_from_vector_db}`部分。
3.  **首次生成SQL**: LLM分析到需要先从`集团信息表`找到“大理矿业公司”的负责人，再用负责人的信息去`高管信息表`查身份证，因此生成一个`JOIN`查询：
    ```sql
    SELECT T2.id_card_number
    FROM group_company_info T1
    JOIN executive_info T2 ON T1.responsible_person_name = T2.name
    WHERE T1.company_name = '大理矿业公司';
    ```
4.  **执行与修复**:
      * **假设场景1：执行成功**。系统直接返回SQL和查询结果。
      * **假设场景2：执行失败**。MySQL报错`Unknown column 'responsible_person_name' in 'group_company_info'`。
      * **自愈**: 系统捕获错误，构建修复Prompt，将失败的SQL和错误信息发给LLM。
      * **再次生成**: LLM看到错误后，对照Schema发现`group_company_info`表中负责人字段名其实是`legal_representative`，于是生成修正后的SQL：
        ```sql
        SELECT T2.id_card_number
        FROM group_company_info T1
        JOIN executive_info T2 ON T1.legal_representative = T2.name
        WHERE T1.company_name = '大理矿业公司';
        ```
      * 系统再次执行，成功后返回结果。

### 5\. 连接Docker中的MySQL数据库

在项目中，你需要从Python后端服务连接到运行在Docker容器里的MySQL。这非常简单，关键在于**端口映射**和**主机地址**。

假设你的`docker run`或者`docker-compose.yml`中设置了端口映射，例如：`-p 3307:3306`。这意味着你把Docker容器的`3306`端口映射到了你宿主机（你运行代码的机器）的`3307`端口。

**连接步骤**:

1.  **确认端口映射**: 在你的终端运行 `docker ps`，找到MySQL容器那一行，查看`PORTS`列。

    ```bash
    $ docker ps
    CONTAINER ID   IMAGE          COMMAND                  CREATED       STATUS       PORTS                               NAMES
    f1a2b3c4d5e6   mysql:8.0      "docker-entrypoint.s…"   2 hours ago   Up 2 hours   0.0.0.0:3307->3306/tcp, 33060/tcp   my-mysql-container
    ```

    这里的`0.0.0.0:3307->3306/tcp`告诉我们，容器的3306端口映射到了宿主机的3307端口。

2.  **编写Python连接代码**:

      * **主机(Host)**: 使用`127.0.0.1`或`localhost`，因为你的Python代码是运行在宿主机上的，它需要访问宿主机的端口。
      * **端口(Port)**: 使用你映射出来的宿主机端口，在上面的例子中是`3307`。
      * **用户(User)**, **密码(Password)**, **数据库(Database)**: 使用你创建MySQL容器时设置的凭据。

**Python代码示例 (使用 `pymysql` 库)**:

首先安装库: `pip install pymysql`

```python
import pymysql

# --- 数据库连接配置 ---
# 注意：这些信息应该从环境变量或配置文件中读取，而不是硬编码
DB_CONFIG = {
    'host': '127.0.0.1',  # 或者 'localhost'
    'port': 3307,         # !!! 使用你映射到宿主机的端口
    'user': 'your_mysql_user',      # 你设置的MySQL用户名
    'password': 'your_mysql_password',# 你设置的MySQL密码
    'database': 'customer_risk_db', # 你要连接的数据库名
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor # 返回结果为字典形式，更方便
}

def execute_sql(sql_query):
    """
    执行SQL查询并返回结果。
    如果执行失败，则捕获异常并返回错误信息。
    """
    connection = None
    try:
        # 建立连接
        connection = pymysql.connect(**DB_CONFIG)
        
        with connection.cursor() as cursor:
            # 执行SQL
            cursor.execute(sql_query)
            
            # 获取查询结果
            result = cursor.fetchall()
            
            # 获取列名
            column_names = [i[0] for i in cursor.description]

            return {
                "success": True,
                "data": result,
                "columns": column_names,
                "error": None
            }

    except pymysql.MySQLError as e:
        # 捕获所有pymysql相关的错误
        error_code, error_message = e.args
        print(f"SQL执行失败! \n错误码: {error_code}\n错误信息: {error_message}")
        return {
            "success": False,
            "data": None,
            "columns": None,
            "error": f"Error {error_code}: {error_message}"
        }
    finally:
        # 确保连接被关闭
        if connection:
            connection.close()

# --- NL2SQL自愈循环的伪代码 ---
def nl2sql_self_healing_loop(user_question):
    max_retries = 3
    current_sql = ""
    last_error = ""

    for attempt in range(max_retries):
        print(f"--- 第 {attempt + 1} 次尝试 ---")
        
        # 1. 生成SQL (这里用伪代码代替LLM调用)
        # prompt = build_prompt(user_question, schema, last_sql=current_sql, error=last_error)
        # current_sql = call_llm(prompt)
        if attempt == 0:
            current_sql = "SELECT T2.id_card_number FROM group_company_info T1 JOIN executive_info T2 ON T1.responsible_person_name = T2.name WHERE T1.company_name = '大理矿业公司';"
        else:
            # 模拟LLM修复SQL
            current_sql = "SELECT T2.id_card_number FROM group_company_info T1 JOIN executive_info T2 ON T1.legal_representative = T2.name WHERE T1.company_name = '大理矿业公司';"

        print(f"生成的SQL: {current_sql}")

        # 2. 执行SQL
        result = execute_sql(current_sql)

        # 3. 判断结果
        if result["success"]:
            print("SQL执行成功!")
            return {"final_sql": current_sql, "result": result["data"]}
        else:
            print("SQL执行失败，准备重试...")
            last_error = result["error"]
    
    print("达到最大重试次数，查询失败。")
    return {"final_sql": current_sql, "error": last_error}

# 调用示例
# nl2sql_self_healing_loop("查看客户风险模块大理矿业公司负责人身份证号")

```

### 6\. 技术选型建议

  * **后端框架**: **Python (FastAPI / Flask)** - Python拥有丰富的AI和数据科学生态，FastAPI性能高，异步支持好，非常适合做API服务。
  * **LLM模型**: **Google Gemini API / OpenAI GPT-4 API** - 作为项目初期的首选，可以快速实现高质量的Text2SQL转换，无需自己训练模型。
  * **向量数据库**: **ChromaDB / FAISS** - ChromaDB非常轻量级，易于上手和部署。FAISS是Facebook的库，性能极高，适合大规模向量检索。
  * **数据库ORM/驱动**: **Pymysql / SQLAlchemy** - Pymysql是纯Python的MySQL驱动，简单直接。SQLAlchemy功能更强大，提供了ORM能力。
  * **前端框架 (可选)**: **Streamlit** (用于快速搭建Demo) / **React 或 Vue** (用于构建正式产品)。

### 7\. 开发路线图

1.  **阶段一：MVP（最小可行产品）**

      * **目标**: 实现核心的Text2SQL转换与执行功能。
      * **任务**:
          * 搭建Python FastAPI后端服务。
          * 手动整理核心表的Schema信息，并编写Prompt模板。
          * 集成LLM API (Gemini/GPT)。
          * 实现到Docker MySQL的连接与SQL执行模块。
          * 提供一个简单的API接口进行测试。

2.  **阶段二：增强核心能力**

      * **目标**: 实现Schema自动化和SQL自愈能力。
      * **任务**:
          * 开发Schema自动抽取和向量化脚本。
          * 集成向量数据库（ChromaDB），实现基于相似度的Schema检索。
          * 实现SQL执行失败后的错误捕获和重试逻辑（自愈循环）。
          * 完善日志和监控。

3.  **阶段三：提升用户体验**

      * **目标**: 支持多轮对话并提供可视化界面。
      * **任务**:
          * 引入对话历史管理机制，支持上下文理解。
          * 使用Streamlit或React/Vue开发一个简单的前端界面。
          * 对查询结果进行格式化展示（例如表格）。

4.  **阶段四：优化与扩展**

      * **目标**: 提升系统性能、准确率和安全性。
      * **任务**:
          * 对Prompt进行持续优化（Prompt Engineering）。
          * 考虑对特定业务场景进行模型微调（Fine-tuning）。
          * 增加安全过滤，防止SQL注入等攻击。
          * 性能优化，如增加缓存策略。

### 8\. 风险与挑战

  * **SQL准确率**: LLM生成复杂SQL（如多层嵌套、窗口函数）时准确率可能会下降，需要持续优化Prompt和Schema描述。
  * **安全性**: 必须对用户输入和LLM生成的SQL进行严格的审查，防止SQL注入等恶意攻击。可以考虑使用权限受限的数据库只读账号。
  * **幻觉问题**: LLM可能会“幻想”出不存在的表或字段，通过在Prompt中严格限定Schema可以缓解此问题。
  * **成本**: 调用商业LLM API会产生费用，需要监控和管理API调用量。

这份技术方案为您提供了一个全面而可行的项目蓝图。祝您项目顺利！