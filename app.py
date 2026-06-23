from html import escape

import streamlit as st

from src.data.akshare_provider import default_provider
from src.pipeline import AnalysisBundle
from src.pipeline import run_analysis
from src.portfolio import (
    add_watchlist_item,
    holding_item_from_search,
    load_portfolio,
    portfolio_item_from_search,
    remove_holding_item,
    remove_watchlist_item,
    upsert_holding_item,
)
from src.types import StockSearchResult
from src.ui.blocks import (
    inject_dashboard_css,
    render_analysis_grid,
    render_result_legend,
    render_score_hero,
    render_technical_snapshot,
)
from src.ui.chart import render_chart
from src.ui.report import build_report

_MARKET_CN = {
    "a_share": "A股",
    "hk": "港股",
    "us": "美股",
}

_US_TECH_LEADERS = [
    ("NVDA", "NVIDIA", "AI GPU / 加速计算", "AI 算力核心"),
    ("MSFT", "Microsoft", "云计算 / AI 软件", "企业软件龙头"),
    ("AAPL", "Apple", "消费电子 / 芯片生态", "硬件生态龙头"),
    ("GOOGL", "Alphabet", "搜索 / AI / 云", "AI 平台龙头"),
    ("AMZN", "Amazon", "AWS / 云基础设施", "云计算龙头"),
    ("META", "Meta", "AI / 社交广告", "广告与 AI 基建"),
    ("AVGO", "Broadcom", "半导体 / 网络芯片", "AI 网络芯片"),
    ("AMD", "AMD", "CPU / GPU", "高性能计算"),
    ("TSM", "台积电 ADR", "先进制程 / 代工", "半导体制造龙头"),
]

_HK_TECH_LEADERS = [
    ("00700", "腾讯控股", "游戏 / 云 / AI", "互联网平台龙头"),
    ("09988", "阿里巴巴-W", "云计算 / 电商 / AI", "云与平台经济"),
    ("09888", "百度集团-SW", "AI / 自动驾驶 / 搜索", "AI 应用龙头"),
    ("03690", "美团-W", "本地生活 / 即时配送", "平台科技龙头"),
    ("09618", "京东集团-SW", "供应链 / 零售科技", "物流科技龙头"),
    ("01810", "小米集团-W", "手机 / IoT / 智能汽车", "硬件生态"),
    ("00981", "中芯国际", "晶圆代工", "国产半导体制造"),
    ("01347", "华虹半导体", "特色工艺半导体", "晶圆制造"),
    ("02382", "舜宇光学科技", "光学 / 车载镜头", "精密硬件"),
]


@st.cache_resource
def _provider():
    return default_provider()


@st.cache_data(ttl=3600, show_spinner=False)
def _search_symbols(query: str) -> list[StockSearchResult]:
    return _provider().search_symbols(query, limit=8)


@st.cache_data(ttl=900, show_spinner=False)
def _run_analysis_cached(code: str):
    return run_analysis(code, provider=_provider())


def _format_result(result: StockSearchResult) -> str:
    market_cn = _MARKET_CN.get(result.market.value, result.market.value)
    return f"{result.code} · {result.name} · {market_cn}"


def _format_search_option(option) -> str:
    if isinstance(option, StockSearchResult):
        return _format_result(option)
    return str(option)


def _fmt_money(value) -> str:
    if value is None:
        return "NA"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "NA"


def _resolve_first_stock(query: str) -> StockSearchResult | None:
    query = query.strip()
    if not query:
        return None
    matches = _search_symbols(query)
    return matches[0] if matches else None


def _render_sidebar_stock_picker(label: str, key_prefix: str) -> StockSearchResult | None:
    query_key = f"{key_prefix}_query"
    select_key = f"{key_prefix}_select"
    query = st.session_state.get(query_key, "")
    matches = _search_symbols(query) if query else []
    selected = st.selectbox(
        label,
        matches,
        index=0 if matches else None,
        format_func=_format_search_option,
        key=select_key,
        placeholder="输入中文名、英文名或代码搜索股票",
        accept_new_options=True,
        filter_mode="fuzzy",
    )

    if isinstance(selected, StockSearchResult):
        st.session_state[query_key] = selected.code
        st.caption(f"已选择：**{_format_result(selected)}**")
        return selected

    typed = str(selected or "").strip()
    if typed and typed != query:
        st.session_state[query_key] = typed
        st.rerun()

    typed_matches = _search_symbols(typed) if typed else []
    if typed_matches:
        st.caption(f"将保存：**{_format_result(typed_matches[0])}**")
        return typed_matches[0]
    if typed:
        st.caption("暂未匹配到股票，请输入更完整的中文名、英文名或代码")
    return None


def _clear_portfolio_cache() -> None:
    _run_analysis_cached.clear()


def _request_analysis_for_code(code: str) -> None:
    st.session_state.stock_query = code
    st.session_state.search_analysis_requested = True


def _friendly_item_name(item) -> str:
    raw_name = (item.name or "").strip()
    if raw_name and raw_name.upper() != item.code.upper():
        return raw_name
    matches = _search_symbols(item.code)
    if matches:
        return matches[0].name
    return raw_name or item.code


def _render_saved_table_header(holding: bool = False) -> None:
    if holding:
        labels = ("股票", "持仓/成本", "", "")
        ratios = [2.2, 1.35, 0.8, 0.8]
    else:
        labels = ("股票", "市场", "", "")
        ratios = [2.7, 0.85, 0.8, 0.8]
    cols = st.columns(ratios, gap="small")
    for col, label in zip(cols, labels):
        col.markdown(f'<div class="aistock-sidebar-th">{escape(label)}</div>', unsafe_allow_html=True)


def _render_saved_item(item, key_prefix: str, holding: bool = False) -> None:
    market_cn = _MARKET_CN.get(item.market.value, item.market.value)
    name = _friendly_item_name(item)
    if holding:
        ratios = [2.2, 1.35, 0.8, 0.8]
        middle = (
            f'<div class="aistock-sidebar-pos">{float(item.quantity):g} 股</div>'
            f'<div class="aistock-sidebar-sub">成本 {_fmt_money(item.cost_price)}</div>'
        )
    else:
        ratios = [2.7, 0.85, 0.8, 0.8]
        middle = f'<div class="aistock-sidebar-market-cell">{escape(market_cn)}</div>'

    cols = st.columns(ratios, gap="small")
    cols[0].markdown(
        f"""
        <div class="aistock-sidebar-stock-cell">
            <span class="aistock-sidebar-code-inline">{escape(item.code)}</span>
            <span class="aistock-sidebar-name-inline">{escape(name)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cols[1].markdown(f'<div class="aistock-sidebar-mid-cell">{middle}</div>', unsafe_allow_html=True)
    if cols[2].button("析", key=f"{key_prefix}_saved_analyze_{item.code}", use_container_width=True, type="primary"):
        _request_analysis_for_code(item.code)
        st.rerun()
    if cols[3].button("删", key=f"{key_prefix}_saved_delete_{item.code}", use_container_width=True):
        if holding:
            remove_holding_item(item.code)
        else:
            remove_watchlist_item(item.code)
        _clear_portfolio_cache()
        st.rerun()
    st.markdown('<div class="aistock-sidebar-row-line"></div>', unsafe_allow_html=True)


def _render_portfolio_sidebar() -> None:
    state = load_portfolio()
    with st.sidebar:
        st.markdown("### 我的股票")

        watchlist_count = len(state.watchlist) if state.watchlist else 0
        with st.expander(f"我的自选（{watchlist_count}）", expanded=False):
            result = _render_sidebar_stock_picker("股票代码或名称", "watchlist_add")
            if st.button("加入自选", key="watchlist_add_btn", use_container_width=True, disabled=result is None):
                if result is None:
                    st.error("未匹配到股票，请输入更完整的代码或名称")
                else:
                    add_watchlist_item(portfolio_item_from_search(result))
                    _clear_portfolio_cache()
                    st.success(f"已加入：{_format_result(result)}")
                    st.rerun()

            st.markdown("---")
            if state.watchlist:
                _render_saved_table_header(holding=False)
                for item in state.watchlist:
                    _render_saved_item(item, "watchlist", holding=False)
            else:
                st.caption("还没有自选股")

        holdings_count = len(state.holdings) if state.holdings else 0
        with st.expander(f"我的持仓（{holdings_count}）", expanded=False):
            result = _render_sidebar_stock_picker("持仓股票代码或名称", "holding_add")
            quantity = st.number_input("数量", min_value=0.0, value=0.0, step=1.0, key="holding_quantity")
            cost_price = st.number_input("成本价", min_value=0.0, value=0.0, step=0.1, key="holding_cost")
            can_save_holding = result is not None and quantity > 0 and cost_price > 0
            if st.button("保存持仓", key="holding_add_btn", use_container_width=True, disabled=not can_save_holding):
                if result is None:
                    st.error("未匹配到股票，请输入更完整的代码或名称")
                elif quantity <= 0 or cost_price <= 0:
                    st.error("数量和成本价必须大于 0")
                else:
                    upsert_holding_item(holding_item_from_search(result, quantity, cost_price))
                    _clear_portfolio_cache()
                    st.success(f"已保存：{_format_result(result)}")
                    st.rerun()

            st.markdown("---")
            if state.holdings:
                _render_saved_table_header(holding=True)
                for item in state.holdings:
                    _render_saved_item(item, "holding", holding=True)
            else:
                st.caption("还没有持仓记录")


def _request_search_analysis() -> None:
    st.session_state.search_analysis_requested = True


def _render_market_hint(query: str, matches: list[StockSearchResult]) -> None:
    if not query.strip():
        st.caption("输入中文名、英文名或代码后，系统会自动匹配最可能的股票")
        return
    if matches:
        st.caption(f"将分析：**{_format_result(matches[0])}**")
    else:
        st.caption("暂未匹配到股票，请输入更完整的中文名、英文名或代码")


def _render_stock_search() -> tuple[str, str]:
    query = st.session_state.get("stock_query", "")
    matches = _search_symbols(query) if query else []
    selected = st.selectbox(
        "请输入股票代码或名称",
        matches,
        index=0 if matches else None,
        format_func=_format_search_option,
        key="stock_search_select",
        placeholder="输入中文名、英文名或代码搜索股票",
        accept_new_options=True,
        filter_mode="fuzzy",
        on_change=_request_search_analysis,
    )

    if isinstance(selected, StockSearchResult):
        st.session_state.stock_query = selected.code
        st.caption(f"将分析：**{_format_result(selected)}**")
        return selected.code, selected.name

    typed = str(selected or "").strip()
    if typed and typed != query:
        st.session_state.stock_query = typed
        st.session_state.search_analysis_requested = True
        st.rerun()

    typed_matches = _search_symbols(typed) if typed else []
    _render_market_hint(typed, typed_matches)
    selected_code = typed_matches[0].code if typed_matches else typed
    return selected_code, typed


def _clean_error(message: str) -> str:
    return message.rstrip("。.")


def _is_resolution_error(message: str) -> bool:
    return any(token in message for token in ("未找到匹配股票", "无法识别的股票代码", "请输入股票代码或名称"))


def _render_analysis_bundle(bundle: AnalysisBundle, display_query: str = "") -> None:
    klines = bundle.kline_result.klines
    last_close = float(klines["close"].iloc[-1]) if not klines.empty else None

    st.markdown("---")
    st.info(
        f"已识别为：{bundle.info.code} · {bundle.info.name} · "
        f"{_MARKET_CN.get(bundle.info.market.value, bundle.info.market.value)}"
    )
    render_technical_snapshot(
        bundle.kline_result,
        bundle.bollinger_result,
        bundle.fibonacci_result,
        bundle.price_action_result,
        bundle.data_quality,
        bundle.option_result,
        bundle.level_result,
    )

    st.markdown("#### 🎯 综合诊断")
    render_score_hero(
        bundle.composite_result,
        bundle.info,
        last_close,
        bundle.data_quality,
    )

    st.markdown("")
    st.markdown("#### 🔍 五维分析")
    render_analysis_grid(
        bundle.value_result,
        bundle.bollinger_result,
        bundle.fibonacci_result,
        bundle.price_action_result,
        bundle.fundamentals,
        bundle.option_result,
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
            bundle.price_action_result,
            bundle.composite_result,
            bundle.data_quality,
            bundle.option_result,
            bundle.level_result,
        )
        st.markdown(report_md)


def _run_and_render_analysis(code: str, display_query: str) -> None:
    try:
        with st.spinner("正在获取数据并分析..."):
            bundle = _run_analysis_cached(code)
    except ValueError as e:
        message = _clean_error(str(e))
        if _is_resolution_error(message):
            st.error(
                f"无法识别股票：{display_query}，请检查输入。"
                f"支持代码或名称关键词，例如 AAPL / 苹果 / 00700 / 腾讯"
            )
        else:
            st.error(f"行情样本不足或分析条件不满足：{message}。请等待更多交易日数据后再试。")
        st.stop()
    except RuntimeError as e:
        st.error(f"数据获取失败：{_clean_error(str(e))}。请稍后重试或换一个候选。")
        st.stop()
    except Exception as e:
        st.error(f"分析过程出错：{e}")
        st.stop()

    _render_analysis_bundle(bundle, display_query)


def _render_leaderboard_group(title: str, rows: list[tuple[str, str, str, str]]) -> None:
    st.markdown(f"#### {title}")
    for code, name, sector, thesis in rows:
        cols = st.columns([1.1, 1.5, 1.8, 1.8, 0.9])
        cols[0].markdown(f"**{code}**")
        cols[1].markdown(name)
        cols[2].caption(sector)
        cols[3].caption(thesis)
        if cols[4].button("分析", key=f"leader_analyze_{code}", use_container_width=True):
            st.session_state.leader_analysis_code = code
            st.session_state.leader_analysis_name = name


def _render_tech_leaderboard() -> None:
    st.caption("科技龙头观察榜按代表性业务整理，不构成投资建议。点击“分析”会直接运行价值、布林带、斐波那契、Price Action 和期权模型。")
    market_tab_us, market_tab_hk = st.tabs(["美股科技龙头", "港股科技龙头"])
    with market_tab_us:
        _render_leaderboard_group("美股热门硬核科技", _US_TECH_LEADERS)
    with market_tab_hk:
        _render_leaderboard_group("港股热门硬核科技", _HK_TECH_LEADERS)

    code = st.session_state.get("leader_analysis_code")
    if code:
        name = st.session_state.get("leader_analysis_name", code)
        st.markdown(f"### {code} · {name}")
        _run_and_render_analysis(code, name)


st.set_page_config(page_title="股票多维分析系统", layout="wide")

inject_dashboard_css()

st.markdown(
    "<div style='display:flex; align-items:center; gap:10px;'>"
    "<h1 style='margin:0;'>📈 股票多维分析系统</h1>"
    "<span style='color:#94a3b8; font-size:13px;'>Dashboard</span>"
    "</div>",
    unsafe_allow_html=True,
)
st.caption("支持 A股（600519）、港股（00700）、美股（AAPL）— 价值分析 · 布林带 · 斐波那契 · Price Action · 期权情绪五维块状仪表盘")
render_result_legend()
_render_portfolio_sidebar()

analysis_tab, leaderboard_tab = st.tabs(["个股分析", "科技龙头榜"])

with analysis_tab:
    with st.container():
        cols = st.columns([4, 1])
        with cols[0]:
            selected_code, display_query = _render_stock_search()
        with cols[1]:
            st.write("")
            st.write("")
            btn = st.button("🚀 开始分析", use_container_width=True)

    search_requested = bool(st.session_state.pop("search_analysis_requested", False))
    if (btn or search_requested) and selected_code:
        _run_and_render_analysis(selected_code, display_query)

with leaderboard_tab:
    _render_tech_leaderboard()

st.markdown("---")
st.caption("本工具基于公开数据自动生成，仅供参考，不构成投资建议。")
