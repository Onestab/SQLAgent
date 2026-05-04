"""
元数据管理模块
负责存储和检索数据库表的业务语义信息
采用混合检索策略：关键词匹配 + 向量检索 + 关联表扩展
"""
import json
import yaml
from pathlib import Path
from typing import Optional, List, Dict, Any, Set, Tuple
import numpy as np
import re


class MetadataManager:
    """元数据管理器，支持混合检索策略"""

    def __init__(self, metadata_dir: str = "./metadata", embedding_model=None):
        self.metadata_dir = Path(metadata_dir)
        self.metadata_dir.mkdir(exist_ok=True)
        self.metadata_cache = {}
        self.embeddings_cache = {}
        self.embedding_model = embedding_model
        self._load_all_metadata()

    def _load_all_metadata(self):
        """加载所有元数据文件"""
        if not self.metadata_dir.exists():
            return

        for yaml_file in self.metadata_dir.glob("*.yaml"):
            table_name = yaml_file.stem
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    metadata = yaml.safe_load(f)
                    if metadata:
                        self.metadata_cache[table_name] = metadata
            except Exception as e:
                print(f"Warning: Failed to load metadata for {table_name}: {e}")

    def _get_embedding_model(self):
        """延迟加载embedding模型"""
        if self.embedding_model is None:
            from config import get_embedding_model
            self.embedding_model = get_embedding_model()
        return self.embedding_model

    def get_table_metadata(self, table_name: str) -> Optional[Dict[str, Any]]:
        """获取表的完整元数据"""
        return self.metadata_cache.get(table_name)

    def get_table_description(self, table_name: str) -> str:
        """获取表的业务描述"""
        metadata = self.get_table_metadata(table_name)
        if metadata:
            return metadata.get("description", "")
        return ""

    def get_column_description(self, table_name: str, column_name: str) -> str:
        """获取列的业务描述"""
        metadata = self.get_table_metadata(table_name)
        if metadata and "columns" in metadata:
            for col in metadata["columns"]:
                if col["name"] == column_name:
                    return col.get("description", "")
        return ""

    def get_business_context(self, table_name: str) -> str:
        """获取表的业务上下文"""
        metadata = self.get_table_metadata(table_name)
        if metadata:
            return metadata.get("business_context", "")
        return ""

    def get_example_queries(self, table_name: str) -> List[Dict[str, str]]:
        """获取示例查询"""
        metadata = self.get_table_metadata(table_name)
        if metadata:
            return metadata.get("example_queries", [])
        return []

    def get_relationships(self, table_name: str) -> List[Dict[str, Any]]:
        """获取表的关联关系"""
        metadata = self.get_table_metadata(table_name)
        if metadata:
            return metadata.get("relationships", [])
        return []

    def get_related_tables(self, table_name: str) -> Set[str]:
        """获取与指定表直接关联的所有表"""
        related = set()
        relationships = self.get_relationships(table_name)
        for rel in relationships:
            related.add(rel.get("target_table"))
        return related

    def _keyword_match_score(self, query: str, table_name: str) -> float:
        """关键词匹配评分"""
        metadata = self.get_table_metadata(table_name)
        if not metadata:
            return 0.0

        query_lower = query.lower()
        score = 0.0

        # 检查表级关键词
        table_keywords = metadata.get("keywords", [])
        for keyword in table_keywords:
            if keyword.lower() in query_lower:
                score += 2.0  # 表级关键词权重高

        # 检查列级关键词
        for col in metadata.get("columns", []):
            col_keywords = col.get("keywords", [])
            for keyword in col_keywords:
                if keyword.lower() in query_lower:
                    score += 1.0  # 列级关键词权重中等

            # 检查列名本身
            if col.get("name", "").lower() in query_lower:
                score += 1.5

        # 检查表名
        if table_name.lower() in query_lower:
            score += 3.0  # 表名匹配权重最高

        # 检查示例查询
        for example in metadata.get("example_queries", []):
            example_question = example.get("question", "").lower()
            # 计算问题相似度（简单的词重叠）
            query_words = set(query_lower.split())
            example_words = set(example_question.split())
            overlap = len(query_words & example_words)
            if overlap > 0:
                score += overlap * 0.5

        return score

    def _vector_search_scores(self, query: str) -> Dict[str, float]:
        """向量检索评分"""
        if not self.metadata_cache:
            return {}

        model = self._get_embedding_model()

        # 根据不同的embedding provider处理
        from config import config
        if config.embedding_provider == "sentence-transformers":
            query_embedding = model.encode([query])[0]
        elif config.embedding_provider in ("vllm", "dashscope"):
            # vLLM和DashScope都使用OpenAI兼容的API
            query_embedding = np.array(model.embed_query(query))
        elif config.embedding_provider == "huggingface":
            query_embedding = np.array(model.embed_query(query))
        else:
            query_embedding = model.encode([query])[0]

        scores = {}
        for table_name, metadata in self.metadata_cache.items():
            if table_name not in self.embeddings_cache:
                # 组合表名、描述、业务上下文、关键词作为检索文本
                text_parts = [
                    table_name,
                    metadata.get("description", ""),
                    metadata.get("business_context", "")
                ]
                # 添加关键词
                text_parts.extend(metadata.get("keywords", []))
                # 添加列名和描述
                for col in metadata.get("columns", []):
                    text_parts.append(col.get("name", ""))
                    text_parts.append(col.get("description", ""))
                    text_parts.extend(col.get("keywords", []))

                combined_text = " ".join(filter(None, text_parts))

                # 根据不同provider生成embedding
                if config.embedding_provider == "sentence-transformers":
                    self.embeddings_cache[table_name] = model.encode([combined_text])[0]
                elif config.embedding_provider in ("vllm", "dashscope"):
                    self.embeddings_cache[table_name] = np.array(model.embed_query(combined_text))
                elif config.embedding_provider == "huggingface":
                    self.embeddings_cache[table_name] = np.array(model.embed_query(combined_text))
                else:
                    self.embeddings_cache[table_name] = model.encode([combined_text])[0]

            # 计算余弦相似度
            table_embedding = self.embeddings_cache[table_name]
            similarity = np.dot(query_embedding, table_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(table_embedding)
            )
            scores[table_name] = similarity

        return scores

    def search_relevant_tables(
        self,
        query: str,
        top_k: int = 3,
        keyword_weight: float = 0.6,
        vector_weight: float = 0.4,
        expand_related: bool = True
    ) -> List[str]:
        """
        混合检索策略：关键词匹配 + 向量检索 + 关联表扩展

        Args:
            query: 用户查询
            top_k: 返回表数量
            keyword_weight: 关键词匹配权重
            vector_weight: 向量检索权重
            expand_related: 是否扩展关联表
        """
        if not self.metadata_cache:
            return []

        # 1. 关键词匹配评分
        keyword_scores = {}
        for table_name in self.metadata_cache.keys():
            keyword_scores[table_name] = self._keyword_match_score(query, table_name)

        # 2. 向量检索评分
        vector_scores = self._vector_search_scores(query)

        # 3. 归一化并融合分数
        max_keyword = max(keyword_scores.values()) if keyword_scores else 1.0
        max_vector = max(vector_scores.values()) if vector_scores else 1.0

        combined_scores = {}
        for table_name in self.metadata_cache.keys():
            kw_score = keyword_scores.get(table_name, 0.0) / max_keyword if max_keyword > 0 else 0.0
            vec_score = vector_scores.get(table_name, 0.0) / max_vector if max_vector > 0 else 0.0
            combined_scores[table_name] = keyword_weight * kw_score + vector_weight * vec_score

        # 4. 排序获取top_k
        sorted_tables = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        selected_tables = [table for table, score in sorted_tables[:top_k]]

        # 5. 扩展关联表（如果启用）
        if expand_related:
            expanded_tables = set(selected_tables)
            for table in selected_tables:
                related = self.get_related_tables(table)
                expanded_tables.update(related)

            # 保持原始顺序，并添加关联表
            result = list(selected_tables)
            for table in expanded_tables:
                if table not in result:
                    result.append(table)

            return result[:top_k * 2]  # 限制扩展后的数量

        return selected_tables

    def get_schema_context(self, table_names: List[str], include_examples: bool = True, include_relationships: bool = True) -> str:
        """生成表的schema上下文，用于LLM"""
        context_parts = []

        for table_name in table_names:
            metadata = self.get_table_metadata(table_name)
            if not metadata:
                continue

            table_context = f"\n## 表: {table_name}\n"
            table_context += f"**描述**: {metadata.get('description', 'N/A')}\n"
            table_context += f"**业务上下文**: {metadata.get('business_context', 'N/A')}\n\n"

            # 添加关联关系信息
            if include_relationships:
                relationships = metadata.get("relationships", [])
                if relationships:
                    table_context += "**关联关系**:\n"
                    for rel in relationships:
                        table_context += f"- {rel.get('join_type', 'unknown')} → {rel.get('target_table', 'unknown')}: "
                        table_context += f"{rel.get('description', 'N/A')}\n"
                        table_context += f"  JOIN条件: {table_name}.{rel.get('foreign_key', '')} = {rel.get('target_table', '')}.{rel.get('target_key', '')}\n"
                    table_context += "\n"

                # 添加常见JOIN路径
                common_joins = metadata.get("common_joins", [])
                if common_joins:
                    table_context += "**常见JOIN路径**:\n"
                    for join in common_joins:
                        table_context += f"- {' → '.join(join.get('tables', []))}\n"
                        table_context += f"  路径: {join.get('path', 'N/A')}\n"
                        table_context += f"  用途: {join.get('use_case', 'N/A')}\n"
                    table_context += "\n"

            table_context += "**列信息**:\n"
            for col in metadata.get("columns", []):
                col_info = f"- {col['name']} ({col.get('type', 'unknown')})"
                if col.get("is_primary_key"):
                    col_info += " [主键]"
                if col.get("is_foreign_key"):
                    col_info += f" [外键 → {col.get('references', 'unknown')}]"
                col_info += f": {col.get('description', 'N/A')}\n"
                table_context += col_info

            if include_examples:
                examples = metadata.get("example_queries", [])
                if examples:
                    table_context += "\n**示例查询**:\n"
                    for ex in examples[:2]:
                        table_context += f"- 问题: {ex.get('question', '')}\n"
                        table_context += f"  SQL: {ex.get('sql', '')}\n"

            context_parts.append(table_context)

        return "\n".join(context_parts)


# 全局实例
metadata_manager = MetadataManager()


def load_metadata():
    """加载元数据管理器"""
    return metadata_manager


def get_table_description(table_name: str) -> str:
    return metadata_manager.get_table_description(table_name)


def get_column_description(table_name: str, column_name: str) -> str:
    return metadata_manager.get_column_description(table_name, column_name)


def get_business_context(table_name: str) -> str:
    return metadata_manager.get_business_context(table_name)
