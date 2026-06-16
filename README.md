# AiStock

基于 Streamlit 的单页股票分析系统，支持 A 股 / 港股 / 美股。通过 AKShare 获取数据，结合价值分析、斐波那契回撤、布林带、Price Action 四大模块给出综合评分。

## 运行

要求 Python 3.10+。如果系统默认 `python` 指向 Python 2，请显式使用 `python3`。

```bash
python3 -m pip install -r requirements.txt
streamlit run app.py
```

## 测试

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```
