import streamlit as st

from src.data.akshare_provider import default_provider
from src.pipeline import run_analysis
from src.types import StockSearchResult
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


@st.cache_resource
def _provider():
    return default_provider()


@st.cache_data(ttl=3600, show_spinner=False)
def _search_symbols(query: str) -> list[StockSearchResult]:
    return _provider().search_symbols(query, limit=8)


def _format_result(result: StockSearchResult) -> str:
    market_cn = _MARKET_CN.get(result.market.value, result.market.value)
    return f"{result.name} · {result.code} · {market_cn}"


def _render_market_hint(query: str, matches: list[StockSearchResult]) -> None:
    if not query.strip():
        st.caption("市场识别：等待输入...")
        return
    try:
        market = detect_market(query)
        market_cn = _MARKET_CN.get(market.value, market.value)
        st.caption(f"市场识别：**{market_cn}** · 可直接按代码分析，也可从候选中选择")
    except ValueError:
        if matches:
            st.caption(f"名称搜索：找到 **{len(matches)}** 个候选，请确认后分析")
        else:
            st.caption("名称搜索：输入代码或名称关键词，例如 600519 / 腾讯 / Apple / 诺基亚")


def _clean_error(message: str) -> str:
    return message.rstrip("。.")


st.set_page_config(page_title="股票多维分析系统", layout="wide")

inject_dashboard_css()

with st.sidebar:
    st.markdown("##### 📡 数据源说明")
    st.caption(
        "行情：新浪财经 / 东方财富 / 腾讯（经 AKShare）。\n\n"
        "若部署在海外服务器（如 Streamlit Cloud），国内行情接口可能因网络/区域限制不可达，"
        "导致查询失败或基本面字段为空。建议在本地运行以获得最稳定体验。"
    )

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
        code = st.text_input("请输入股票代码或名称", placeholder="例如 600519 / 贵州茅台 / 00700 / 腾讯 / AAPL / 苹果 / NOK / 诺基亚")
        matches = _search_symbols(code.strip()) if code.strip() else []
        _render_market_hint(code, matches)
        selected_code = code.strip()
        if matches:
            selected = st.selectbox(
                "匹配结果",
                matches,
                format_func=_format_result,
                label_visibility="collapsed",
            )
            selected_code = selected.code
    with cols[1]:
        st.write("")
        st.write("")
        btn = st.button("🚀 开始分析", use_container_width=True)

if btn and selected_code:
    try:
        with st.spinner("正在获取数据并分析..."):
            bundle = run_analysis(selected_code, provider=_provider())
    except ValueError:
        st.error(
            f"无法识别股票：{code}，请检查输入。"
            f"支持代码或名称关键词，例如 AAPL / 苹果 / 00700 / 腾讯"
        )
        st.stop()
    except RuntimeError as e:
        st.error(f"数据获取失败：{_clean_error(str(e))}。请稍后重试或换一个候选。")
        st.stop()
    except Exception as e:
        st.error(f"分析过程出错：{e}")
        st.stop()

    klines = bundle.kline_result.klines
    last_close = float(klines["close"].iloc[-1]) if not klines.empty else None

    st.markdown("---")
    st.markdown("#### 🎯 综合诊断")
    render_score_hero(
        bundle.composite_result,
        bundle.info,
        last_close,
        bundle.data_quality,
    )

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
            bundle.data_quality,
        )
        st.markdown(report_md)

st.markdown("---")
st.caption("本工具基于公开数据自动生成，仅供参考，不构成投资建议。")
