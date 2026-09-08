"""
The Binance Agent OS MCP server's tool catalog, as observed on 8 September 2026 through an
authenticated Claude connector (73 tools). Binance has not published this list. Names here are
matched exactly; anything not listed falls back to name heuristics and, if still unknown, asks.
"""
ORDER = {
    "spot_newOrder", "margin_marginAccountNewOrder",
    "convert_sendQuoteRequest", "convert_placeLimitOrder",
}
ORDER_ACCEPT = {"convert_acceptQuote"}          # executes a previously judged quote; carries only quoteId
CANCEL = {
    "spot_deleteOrder", "spot_deleteOpenOrders", "margin_marginAccountCancelOrder",
    "margin_marginAccountCancelAllOpenOrdersOnASymbol", "convert_cancelLimitOrder",
}
TRANSFER = {"wallet_userUniversalTransfer", "margin_marginAccountBorrowRepay"}
PROXY = {"tool_execute"}                         # can invoke any other tool by name
READ = {
    "tool_search", "analysis_getTokenAiReport",
    "spot_depth", "spot_exchangeInfo", "spot_klines", "spot_uiKlines", "spot_ticker24hr", "spot_tickerPrice",
    "spot_getAccount", "spot_getOpenOrders", "spot_getOrder", "spot_myTrades",
    "margin_crossMarginCollateralRatio", "margin_getAllIsolatedMarginSymbol", "margin_getAllMarginAssets",
    "margin_queryCrossMarginAccountDetails", "margin_queryMaxBorrow", "margin_queryMarginAccountsAllOrders",
    "margin_queryMarginAccountsOpenOrders", "margin_queryMarginAccountsOrder", "margin_queryMarginAccountsTradeList",
    "convert_listAllConvertPairs", "convert_queryOrderQuantityPrecisionPerAsset", "convert_orderStatus",
    "convert_queryLimitOpenOrders", "convert_getConvertTradeHistory",
    "futures_usds_exchangeInformation", "futures_usds_symbolPriceTicker", "futures_usds_klineCandlestickData",
    "futures_usds_continuousContractKlineCandlestickData", "futures_usds_indexPriceKlineCandlestickData",
    "futures_usds_markPriceKlineCandlestickData", "futures_usds_premiumIndexKlineData",
    "futures_usds_accountInformationV3", "futures_usds_futuresAccountBalanceV3", "futures_usds_positionInformationV2",
    "futures_usds_currentAllOpenOrders", "futures_usds_queryOrder",
    "futures_coin_exchangeInformation", "futures_coin_symbolPriceTicker", "futures_coin_klineCandlestickData",
    "futures_coin_continuousContractKlineCandlestickData", "futures_coin_indexPriceKlineCandlestickData",
    "futures_coin_markPriceKlineCandlestickData", "futures_coin_premiumIndexKlineData",
    "futures_coin_accountInformation", "futures_coin_futuresAccountBalance", "futures_coin_positionInformation",
    "futures_coin_currentAllOpenOrders", "futures_coin_queryOrder",
    "wallet_accountStatus", "wallet_getApiKeyPermission", "wallet_allCoinsInformation", "wallet_queryUserWalletBalance",
    "wallet_dailyAccountSnapshot", "wallet_depositAddress", "wallet_depositHistory", "wallet_withdrawHistory",
    "wallet_queryUserUniversalTransferHistory", "sub_account_getMainAccountAsset",
}
ALL = ORDER | ORDER_ACCEPT | CANCEL | TRANSFER | PROXY | READ


def category(tool: str):
    """Exact category for a bare tool name (without the mcp__server__ prefix), or None."""
    if tool in ORDER:
        return "order"
    if tool in ORDER_ACCEPT:
        return "order_accept"
    if tool in CANCEL:
        return "cancel"
    if tool in TRANSFER:
        return "transfer"
    if tool in PROXY:
        return "proxy"
    if tool in READ:
        return "read"
    return None
