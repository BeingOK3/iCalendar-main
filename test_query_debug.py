#!/usr/bin/env python3
"""
简单的日程查询测试脚本
用于诊断自然语言查询问题
"""

import httpx
import json
import time

def test_query(text):
    """测试查询功能"""
    print(f"\n{'='*60}")
    print(f"测试查询: {text}")
    print(f"{'='*60}")
    
    try:
        response = httpx.post(
            "http://localhost:8000/api/nl/execute",
            json={"text": text, "session_id": "debug_session"},
            timeout=30.0
        )
        
        print(f"状态码: {response.status_code}")
        result = response.json()
        print(f"响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
        
        return result
        
    except Exception as e:
        print(f"错误: {e}")
        return None

if __name__ == "__main__":
    print("\n🔍 开始诊断日程查询功能")
    print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 等待服务器启动
    print("\n等待服务器启动...")
    time.sleep(2)
    
    # 测试不同的查询
    queries = [
        "查看今天的日程",
        "查看明天的日程",
        "查看本周的日程",
        "今天有什么安排？",
    ]
    
    for query in queries:
        test_query(query)
        time.sleep(1)
    
    print(f"\n{'='*60}")
    print("测试完成！请查看服务器日志了解详细信息")
    print(f"{'='*60}\n")
