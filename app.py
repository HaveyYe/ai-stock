import streamlit as st

from src.pipeline import run_analysis
from src.ui.blocks import (
    inject_dashboard_css,
    render_analysis_grid,
    render_score_hero,
)
from src.ui.chart import render_chart
from src.ui.report import build_report
from src.utils.market_detector import detect_market

_MARKET_CN = {
    "a_share": "A股",
    "hk": "港股",
    "us": "美股",
}


def _render_market_hint(code: str) -> None:
    if not code.strip():
        st.caption("市场识别：等待输入...")
        return
    try:
        market = detect_market(code)
        market_cn = _MARKET_CN.get(market.value, market.value)
        st.caption(f"市场识别：**{market_cn}**")
    except ValueError:
        st.caption("市场识别：无法识别，请检查代码格式")


st.set_page_config(page_title="股票多维分析系统", layout="wide")

inject_dashboard_css()

st.markdown(
    "<div style='display:flex; align-items:center; gap:10px;'>"
    "<h1 style='margin:0;'>📈 股票多维分析系统</h1>"
    "<span style='color:#94a3b8; font-size:13px;'>Dashboard</span>"
    "</div>",
    unsafe_allow_html=True,
)
st.caption("支持 A股（600519）、港股（00700）、美股（AAPL）— 价值分析 · 布林带 · 斐波那契 三维块状仪表盘")

with st.container():
    cols = st.columns([4, 1])
    with cols[0]:
        code = st.text_input("请输入股票代码", placeholder="例如 600519 / 00700 / AAPL / AAPL.US / 00700.HK")
        _render_market_hint(code)
    with cols[1]:
        st.write("")
        st.write("")
        btn = st.button("🚀 开始分析", use_container_width=True)

if btn and code:
    try:
        with st.spinner("正在获取数据并分析..."):
            bundle = run_analysis(code.strip())
    except ValueError:
        st.error(
            f"无法识别股票代码：{code}，请检查输入。"
            f"支持 A股(6位数字)/港股(5位数字)/美股(字母代码)"
        )
        st.stop()
    except RuntimeError as e:
        st.error(f"数据获取失败：{e}。请稍后重试或检查网络。")
        st.stop()
    except Exception as e:
        st.error(f"分析过程出错：{e}")
        st.stop()

    klines = bundle.kline_result.klines
    last_close = float(klines["close"].iloc[-1]) if not klines.empty else None

    st.markdown("---")
    st.markdown("#### 🎯 综合诊断")
    render_score_hero(bundle.composite_result, bundle.info, last_close)

    st.markdown("")
    st.markdown("#### 🔍 三维分析")
    render_analysis_grid(
        bundle.value_result,
        bundle.bollinger_result,
        bundle.fibonacci_result,
        bundle.fundamentals,
    )

    st.markdown("")
    st.markdown("#### 📊 K 线技术分析图")
    fig = render_chart(
        bundle.kline_result,
        bundle.bollinger_result,
        bundle.fibonacci_result,
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📝 查看完整文字报告", expanded=False):
        report_md = build_report(
            bundle.info,
            bundle.fundamentals,
            bundle.value_result,
            bundle.bollinger_result,
            bundle.fibonacci_result,
            bundle.composite_result,
        )
        st.markdown(report_md)

st.markdown("---")
st.caption("本工具基于公开数据自动生成，仅供参考，不构成投资建议。")
