# The Binance Agent OS MCP server's tools, as observed

Binance has not published the tool list for `https://agent.binance.com/mcp/agentic`. This is what an
authenticated Claude connector reported on 8 September 2026 (73 tools), with the scopes Market data and
Account granted. The hook in `secondopinion/hook/binance_tools.py` matches these names exactly.

## How Second Opinion treats each group

| group | tools | hook behaviour |
| --- | --- | --- |
| Places a market bet | `spot_newOrder`, `margin_marginAccountNewOrder`, `convert_sendQuoteRequest`, `convert_placeLimitOrder` | judged: APPROVE allows, CAUTION and VETO deny with the receipt |
| Executes a judged bet | `convert_acceptQuote` | allowed only if a `convert_sendQuoteRequest` was approved in the last 15 minutes; carries only a `quoteId`, so the judgment happens at the quote |
| Proxy | `tool_execute` | unwrapped: the inner `toolName` and `arguments` are judged as if called directly, so the proxy cannot bypass the gate |
| Reduces or moves risk | `spot_deleteOrder`, `spot_deleteOpenOrders`, `margin_marginAccountCancelOrder`, `margin_marginAccountCancelAllOpenOrdersOnASymbol`, `convert_cancelLimitOrder`, `wallet_userUniversalTransfer`, `margin_marginAccountBorrowRepay` | allowed and logged; not a market bet |
| Read-only | the other 60 | allowed silently |
| Not in the catalog | anything else | asks; never a silent allow |

Notable: there are no futures order tools in the catalog despite the docs mentioning futures trading, and no
withdraw tool, consistent with Binance's "no withdrawal scope" guarantee. `tool_search` plus `tool_execute`
suggest a larger hidden set; the hook treats any inner tool it does not recognise as unknown.

## The catalog

| tool | required | optional |
| --- | --- | --- |
| tool_search | category | cursor |
| tool_execute | toolName | arguments |
| analysis_getTokenAiReport | token | expId, product, timestamp |
| spot_depth | symbol | limit, symbolStatus |
| spot_exchangeInfo | | permissions, showPermissionSets, symbol, symbolStatus, symbols |
| spot_klines | symbol, interval | endTime, limit, startTime, timeZone |
| spot_uiKlines | symbol, interval | endTime, limit, startTime, timeZone |
| spot_ticker24hr | symbol or symbols | symbol, symbols, symbolStatus, type |
| spot_tickerPrice | | symbol, symbols, symbolStatus |
| spot_getAccount | | omitZeroBalances, recvWindow |
| spot_getOpenOrders | | recvWindow, symbol |
| spot_getOrder | symbol | orderId, origClientOrderId, recvWindow |
| spot_myTrades | symbol | endTime, fromId, limit, orderId, recvWindow, startTime |
| spot_newOrder | symbol, side, type | icebergQty, newClientOrderId, newOrderRespType, pegOffsetType, pegOffsetValue, pegPriceType, price, quantity, quoteOrderQty, recvWindow, selfTradePreventionMode, stopPrice, strategyId, strategyType, timeInForce, trailingDelta |
| spot_deleteOrder | symbol | cancelRestrictions, newClientOrderId, orderId, origClientOrderId, recvWindow |
| spot_deleteOpenOrders | symbol | recvWindow |
| margin_crossMarginCollateralRatio | | |
| margin_getAllIsolatedMarginSymbol | | recvWindow, symbol |
| margin_getAllMarginAssets | | asset |
| margin_queryCrossMarginAccountDetails | | recvWindow |
| margin_queryMaxBorrow | asset | isolatedSymbol, recvWindow |
| margin_queryMarginAccountsAllOrders | symbol | endTime, isIsolated, limit, orderId, recvWindow, startTime |
| margin_queryMarginAccountsOpenOrders | | isIsolated, recvWindow, symbol |
| margin_queryMarginAccountsOrder | symbol | isIsolated, orderId, origClientOrderId, recvWindow |
| margin_queryMarginAccountsTradeList | symbol | endTime, fromId, isIsolated, limit, orderId, recvWindow, startTime |
| margin_marginAccountBorrowRepay | asset, isIsolated, amount, type | recvWindow, symbol |
| margin_marginAccountNewOrder | symbol, side, type | autoRepayAtCancel, icebergQty, isIsolated, newClientOrderId, newOrderRespType, price, quantity, quoteOrderQty, recvWindow, selfTradePreventionMode, sideEffectType, stopPrice, timeInForce, trailingDelta |
| margin_marginAccountCancelOrder | symbol | isIsolated, newClientOrderId, orderId, origClientOrderId, recvWindow |
| margin_marginAccountCancelAllOpenOrdersOnASymbol | symbol | isIsolated, recvWindow |
| convert_listAllConvertPairs | fromAsset or toAsset | |
| convert_queryOrderQuantityPrecisionPerAsset | | recvWindow |
| convert_orderStatus | orderId or quoteId | |
| convert_queryLimitOpenOrders | | recvWindow |
| convert_getConvertTradeHistory | startTime, endTime | limit, recvWindow |
| convert_sendQuoteRequest | fromAsset, toAsset | fromAmount, recvWindow, toAmount, validTime, walletType |
| convert_acceptQuote | quoteId | recvWindow |
| convert_placeLimitOrder | baseAsset, quoteAsset, limitPrice, side, expiredType | baseAmount, quoteAmount, recvWindow, walletType |
| convert_cancelLimitOrder | orderId | recvWindow |
| futures_usds_exchangeInformation | | |
| futures_usds_symbolPriceTicker | | symbol |
| futures_usds_klineCandlestickData | symbol, interval | endTime, limit, startTime |
| futures_usds_continuousContractKlineCandlestickData | pair, contractType, interval | endTime, limit, startTime |
| futures_usds_indexPriceKlineCandlestickData | pair, interval | endTime, limit, startTime |
| futures_usds_markPriceKlineCandlestickData | symbol, interval | endTime, limit, startTime |
| futures_usds_premiumIndexKlineData | symbol, interval | endTime, limit, startTime |
| futures_usds_accountInformationV3 | | recvWindow |
| futures_usds_futuresAccountBalanceV3 | | recvWindow |
| futures_usds_positionInformationV2 | | recvWindow, symbol |
| futures_usds_currentAllOpenOrders | | recvWindow, symbol |
| futures_usds_queryOrder | symbol | orderId, origClientOrderId, recvWindow |
| futures_coin_exchangeInformation | | |
| futures_coin_symbolPriceTicker | | pair, symbol |
| futures_coin_klineCandlestickData | symbol, interval | endTime, limit, startTime |
| futures_coin_continuousContractKlineCandlestickData | pair, contractType, interval | endTime, limit, startTime |
| futures_coin_indexPriceKlineCandlestickData | pair, interval | endTime, limit, startTime |
| futures_coin_markPriceKlineCandlestickData | symbol, interval | endTime, limit, startTime |
| futures_coin_premiumIndexKlineData | symbol, interval | endTime, limit, startTime |
| futures_coin_accountInformation | | recvWindow |
| futures_coin_futuresAccountBalance | | recvWindow |
| futures_coin_positionInformation | | marginAsset, pair, recvWindow |
| futures_coin_currentAllOpenOrders | | pair, recvWindow, symbol |
| futures_coin_queryOrder | symbol | orderId, origClientOrderId, recvWindow |
| wallet_accountStatus | | recvWindow |
| wallet_getApiKeyPermission | | recvWindow |
| wallet_allCoinsInformation | | recvWindow |
| wallet_queryUserWalletBalance | | quoteAsset, recvWindow |
| wallet_dailyAccountSnapshot | type | endTime, limit, recvWindow, startTime |
| wallet_depositAddress | coin | amount, network, recvWindow |
| wallet_depositHistory | | coin, endTime, includeSource, limit, offset, recvWindow, startTime, status, txId |
| wallet_withdrawHistory | | coin, endTime, idList, limit, offset, recvWindow, startTime, status, withdrawOrderId |
| wallet_queryUserUniversalTransferHistory | type | current, endTime, fromSymbol, recvWindow, size, startTime, toSymbol |
| wallet_userUniversalTransfer | type, asset, amount | fromSymbol, recvWindow, toSymbol |
| sub_account_getMainAccountAsset | | quoteAsset, recvWindow |

Connection check at the time, raw `spot_ticker24hr` for BTCUSDT: last price 78,761.02, 24h change -0.313%, 24h quote volume 1.46 billion USDT.
